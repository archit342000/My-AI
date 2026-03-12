import asyncio
import os
import time
import json
import logging
import base64
import html
import random
import re
import urllib.parse
from urllib.parse import urlparse, urljoin
import socket
import ipaddress
import io

import httpx
from bs4 import BeautifulSoup
import markdownify
from selectolax.lexbor import LexborHTMLParser
import pypdf

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
import uvicorn

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_server")

# =====================================================================
def get_secret(secret_name, default=None):
    try:
        with open(f"/run/secrets/{secret_name}", "r") as f:
            return f.read().strip()
    except IOError:
        return os.getenv(secret_name, default)

TAVILY_BASE_URL = "https://api.tavily.com"
TAVILY_API_KEY = get_secret("TAVILY_API_KEY", "")
MCP_API_KEY = get_secret("MCP_API_KEY", "")

# Timeouts
TIMEOUT_TAVILY_SEARCH = 15.0
TIMEOUT_TAVILY_SEARCH_ASYNC = 20.0
TIMEOUT_TAVILY_MAP = 30.0
TIMEOUT_TAVILY_EXTRACT = 30.0
TIMEOUT_WEB_SCRAPE = 20.0
TIMEOUT_IMAGE_FETCH = 15.0

# Search Configs
SEARCH_DEPTH = "advanced"
MAX_SEARCH_RESULTS = 10
MIN_SEARCH_RESULTS = 1
RELEVANCE_THRESHOLD = 0.5
INCLUDE_ANSWER = True
INCLUDE_RAW_CONTENT = True
SEARCH_CACHE_TTL = 3600
TAVILY_MAP_MAX_DEPTH = 2
TAVILY_MAP_MAX_BREADTH = 10

URL_FETCH_RETRIES = 3
RESEARCH_IMAGE_FETCH_RETRIES = 2

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

# Simple in-memory cache for audit_search
_tavily_search_cache = {}

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def is_safe_web_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_reserved:
            return False
        return True
    except Exception:
        return False

def _apply_markdown_post_processing(md_text, base_url):
    """Normalizes and prunes markdown content."""
    def make_absolute(match):
        anchor_text = match.group(1)
        href = match.group(2)
        abs_url = urljoin(base_url, href)
        return f"[{anchor_text}]({abs_url})"

    md_text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', make_absolute, md_text)
    md_text = re.sub(r'\[[^\]]*\]\(\s*\)', '', md_text)
    md_text = md_text.replace('\xa0', ' ').replace('\u200b', '')
    md_text = re.sub(r'[ \t]+$', '', md_text, flags=re.MULTILINE)
    md_text = re.sub(r'([*_=]){4,}', r'\1\1\1', md_text)
    md_text = re.sub(r'\n{3,}', '\n\n', md_text)
    return md_text.strip()

def clean_html_to_markdown(html_content, base_url):
    """Strips noise from HTML and converts to clean, prioritized markdown."""
    try:
        parser = LexborHTMLParser(html_content)

        noise_selectors = [
            "script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "meta",
            "iframe", "ins.adsbygoogle", ".ad", ".advertisement", ".banner",
            "[class*='sponsor']", "[id*='taboola']", "[id*='outbrain']"
        ]

        for selector in noise_selectors:
            for node in parser.css(selector):
                node.decompose()

        content_node = None
        for wrapper in ["article", "main", ".main-content", ".post-body"]:
            matches = parser.css(wrapper)
            if matches:
                content_node = matches[0]
                break

        if not content_node:
            content_node = parser.body
        if not content_node:
            content_node = parser.root
        if not content_node:
            return ""

        clean_html = content_node.html

        md_text = markdownify.markdownify(
            clean_html,
            heading_style="ATX",
            strip=['audio', 'video'],
            keep_inline_images_in=['a']
        )

        return _apply_markdown_post_processing(md_text, base_url)
    except Exception as e:
        logger.error(f"Error cleaning HTML: {e}")
        return ""

async def _extract_pdf_content(pdf_bytes):
    try:
        import fitz  # pymupdf
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                pages.append(text.strip())
        doc.close()
        return "\n\n---\n\n".join(pages) if pages else None
    except ImportError:
        logger.warning("pymupdf not installed. Falling back to pypdf.")
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = pypdf.PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text() or ""
                page_text = re.sub(r'(?m)^\s*\d+\s*$', '', page_text)
                text += page_text + "\n"
            if not text.strip():
                return None
            text = text.replace('\r', '\n').replace('\xa0', ' ')
            text = re.sub(r'[ \t]+', ' ', text)
            text = re.sub(r'\n{3,}', '\n\n', text)
            return text.strip()
        except Exception as e:
            logger.error(f"pypdf fallback failed: {e}")
            return None
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return None

# =====================================================================
# CORE TOOL IMPLEMENTATIONS
# =====================================================================

async def execute_tavily_search(query: str, topic: str = "general", time_range: str | None = None,
                               start_date: str | None = None, end_date: str | None = None,
                               include_images: bool = False, chat_id: str | None = None):
    if not TAVILY_API_KEY:
         return "Error: TAVILY_API_KEY is not configured in the MCP Server environment."

    url = f"{TAVILY_BASE_URL}/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": SEARCH_DEPTH,
        "topic": topic if topic in ["general", "news", "finance"] else "general",
        "max_results": MAX_SEARCH_RESULTS,
        "include_answer": INCLUDE_ANSWER,
        "include_raw_content": INCLUDE_RAW_CONTENT,
        "include_images": include_images,
        "include_image_descriptions": False
    }

    if time_range and time_range in ["day", "week", "month", "year", "d", "w", "m", "y"]:
        payload["time_range"] = time_range
    if start_date: payload["start_date"] = start_date
    if end_date: payload["end_date"] = end_date

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_TAVILY_SEARCH_ASYNC) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            answer = data.get("answer", "")
            results = data.get("results", [])
            images = data.get("images", [])

            filtered_results = []
            for res in results:
                score = res.get("score", 0)
                if score >= RELEVANCE_THRESHOLD or len(filtered_results) < MIN_SEARCH_RESULTS:
                    filtered_results.append(res)

            output_parts = []
            if answer:
                output_parts.append(f"AI Summary from Tavily: {answer}\n")

            raw_contents_for_cache = []
            for res in filtered_results:
                title = res.get("title", "No Title")
                href = res.get("url", "")
                content = res.get("content", "")
                raw = res.get("raw_content")
                if raw and ("<html" in raw.lower() or "<body" in raw.lower() or "<div" in raw.lower()):
                    raw = clean_html_to_markdown(raw, href)
                else:
                    raw = _apply_markdown_post_processing(raw or "No raw content available.", href)

                output_parts.append(f"Title: {title}\nLink: {href}\nContent Snippet: {content}")
                raw_contents_for_cache.append(f"Title: {title}\nLink: {href}\nRaw Content:\n{raw}")

            standard_output = "\n---\n".join(output_parts)
            raw_output = "\n================\n".join(raw_contents_for_cache)

            if not standard_output.strip():
                standard_output = "No basic results found."
            if not raw_output.strip():
                raw_output = "No raw content available."

            if chat_id:
                _tavily_search_cache[chat_id] = {
                    "raw_content": raw_output,
                    "timestamp": time.time()
                }

            # Since tools over MCP need to return strings, we'll serialize standard_output and raw_output if needed
            return json.dumps({
                "standard_output": standard_output,
                "raw_output": raw_output,
                "images": images,
                "results": filtered_results
            })
    except Exception as e:
        return json.dumps({"error": f"Tavily search failed: {str(e)}"})

async def audit_tavily_search(chat_id: str):
    if not chat_id or chat_id not in _tavily_search_cache:
        return "Error: No recent search found for this context to audit."

    cache_entry = _tavily_search_cache[chat_id]
    if time.time() - cache_entry["timestamp"] > SEARCH_CACHE_TTL:
        del _tavily_search_cache[chat_id]
        return "Error: The previous search data has expired from cache."

    return cache_entry["raw_content"]

async def async_tavily_search(query: str, topic: str = "general", time_range: str | None = None,
                              start_date: str | None = None, end_date: str | None = None, max_results: int = 10):
    url = f"{TAVILY_BASE_URL}/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "topic": topic if topic in ["general", "news", "finance"] else "general",
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": True,
        "include_images": True
    }
    if time_range and time_range in ["day", "week", "month", "year"]: payload["time_range"] = time_range
    if start_date: payload["start_date"] = start_date
    if end_date: payload["end_date"] = end_date

    async with httpx.AsyncClient(timeout=TIMEOUT_TAVILY_SEARCH_ASYNC) as client:
        try:
             resp = await client.post(url, json=payload)
             resp.raise_for_status()
             data = resp.json()
             return json.dumps({
                 "results": data.get("results", []),
                 "images": data.get("images", [])
             })
        except Exception as e:
             return json.dumps({"error": str(e), "results": [], "images": []})

async def async_tavily_map(url_to_map: str, instruction: str):
    url = f"{TAVILY_BASE_URL}/map"
    payload = {
        "api_key": TAVILY_API_KEY,
        "url": url_to_map,
        "instructions": instruction,
        "max_depth": TAVILY_MAP_MAX_DEPTH,
        "max_breadth": TAVILY_MAP_MAX_BREADTH,
        "limit": TAVILY_MAP_MAX_BREADTH,
        "allow_external": True,
        "exclude_paths": ["/login", "/signup", "/auth"],
        "exclude_domains": ["facebook.com", "twitter.com", "instagram.com"]
    }
    async with httpx.AsyncClient(timeout=TIMEOUT_TAVILY_MAP) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"results": data.get("results", [])})
        except Exception as e:
            return json.dumps({"error": str(e), "results": []})

async def async_tavily_extract(urls: list):
    if not urls: return json.dumps({"results": []})
    url = f"{TAVILY_BASE_URL}/extract"
    payload = {
        "api_key": TAVILY_API_KEY,
        "urls": urls,
        "extract_depth": "basic",
        "include_images": True,
        "format": "markdown"
    }
    async with httpx.AsyncClient(timeout=TIMEOUT_TAVILY_EXTRACT) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return json.dumps({"results": data.get("results", [])})
        except Exception as e:
            return json.dumps({"error": str(e), "results": []})

async def visit_page(url: str, max_chars: int = 40000):
    if not is_safe_web_url(url):
        return "Error: URL is forbidden (SSRF protection). Cannot visit local or private IP addresses."
    try:
        headers = {'User-Agent': random.choice(USER_AGENTS)}

        async with httpx.AsyncClient(headers=headers, timeout=TIMEOUT_WEB_SCRAPE, follow_redirects=False) as client:
            current_url = url
            response = None
            for _ in range(URL_FETCH_RETRIES):
                response = await client.get(current_url)
                if response.status_code in (301, 302, 303, 307, 308):
                    next_url = response.headers.get('Location')
                    if not next_url:
                        break
                    next_url = urljoin(current_url, next_url)
                    if not is_safe_web_url(next_url):
                        return "Error: Redirected URL is forbidden (SSRF protection)."
                    current_url = next_url
                else:
                    break

            if not response:
                return "Error: Could not fetch URL."

            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '').lower()
            if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
                pdf_text = await _extract_pdf_content(response.content)
                if pdf_text:
                    return f"[PDF Document]\n\n{pdf_text[:max_chars]}"
                return "PDF content extracted but appears empty (possibly image-only)."

            text = clean_html_to_markdown(response.text, url)
            if not text:
                 return "Error: Could not find any valid content block on the page."

            return text[:max_chars]

    except Exception as e:
        return f"Error visiting page: {str(e)}"

async def fetch_and_encode_image(url: str):
    if not is_safe_web_url(url):
        return json.dumps({"error": "Unsafe URL"})
    try:
        current_url = url
        resp = None
        headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            'Accept': "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            'Accept-Language': "en-US,en;q=0.9",
            'Referer': f"https://{urllib.parse.urlparse(url).netloc}/"
        }
        async with httpx.AsyncClient(timeout=TIMEOUT_IMAGE_FETCH, follow_redirects=False, headers=headers) as client:
            for _ in range(RESEARCH_IMAGE_FETCH_RETRIES):
                resp = await client.get(current_url)
                if resp.status_code in (301, 302, 303, 307, 308):
                    next_url = resp.headers.get('Location')
                    if not next_url:
                        break
                    next_url = urllib.parse.urljoin(current_url, next_url)
                    if not is_safe_web_url(next_url):
                        return json.dumps({"error": "Unsafe redirect URL"})
                    current_url = next_url
                else:
                    break

            if not resp:
                return json.dumps({"error": "Failed to fetch image"})
            resp.raise_for_status()
            mime = resp.headers.get('content-type', 'image/jpeg').split(';')[0].strip()
            b64 = base64.b64encode(resp.content).decode('utf-8')
            return json.dumps({"image": f"data:{mime};base64,{b64}"})
    except Exception as e:
         return json.dumps({"error": str(e)})

# =====================================================================
# MCP SERVER SETUP (FastMCP)
# =====================================================================

mcp = FastMCP("research_tools_mcp", host="0.0.0.0", port=8000)

# Security Middleware to protect MCP endpoints
from starlette.responses import JSONResponse

class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        # Protect SSE and message routes
        if path in ["/sse", "/messages/"] or path.startswith("/messages/"):
            if MCP_API_KEY:
                # Headers in ASGI scope are raw bytes
                headers = dict(scope.get("headers", []))
                # Check for both lowercase and original case
                api_key_bytes = headers.get(b"x-mcp-api-key")
                if api_key_bytes is None:
                    api_key_bytes = headers.get(b"X-MCP-API-KEY", b"")
                
                api_key = api_key_bytes.decode("utf-8")
                
                if api_key != MCP_API_KEY:
                    logger.warning(f"Unauthorized access attempt to {path}")
                    response = JSONResponse({"error": "Unauthorized"}, status_code=401)
                    await response(scope, receive, send)
                    return
        
        await self.app(scope, receive, send)

@mcp.tool()
async def search_web(query: str, topic: str = "general", time_range: str | None = None,
                     start_date: str | None = None, end_date: str | None = None,
                     include_images: bool = False, chat_id: str | None = None) -> str:
    """Performs a web search using Tavily to find information on a topic. Results include an AI-summarized answer and excerpts from the top sources. Use this tool for normal web searching. If the initial results do not contain enough information, you may use the audit_search tool to get the raw content."""
    res = await execute_tavily_search(query, topic, time_range, start_date, end_date, include_images, chat_id)
    return res

@mcp.tool()
async def audit_search(chat_id: str) -> str:
    """Retrieves the full raw content of the most recently executed web search. Use this ONLY if the summarized content from the previous web search was not detailed enough to answer the user's query."""
    res = await audit_tavily_search(chat_id)
    return res

@mcp.tool()
async def async_tavily_search_tool(query: str, topic: str = "general", time_range: str | None = None,
                              start_date: str | None = None, end_date: str | None = None, max_results: int = 10) -> str:
    """Internal research tool to perform async web searches."""
    res = await async_tavily_search(query, topic, time_range, start_date, end_date, max_results)
    return res

@mcp.tool()
async def async_tavily_map_tool(url_to_map: str, instruction: str) -> str:
    """Internal research tool to map a URL for deep data pages."""
    res = await async_tavily_map(url_to_map, instruction)
    return res

@mcp.tool()
async def async_tavily_extract_tool(urls: list[str]) -> str:
    """Internal research tool to extract content from URLs."""
    res = await async_tavily_extract(urls)
    return res

@mcp.tool()
async def visit_page_tool(url: str, max_chars: int = 40000) -> str:
    """Visits a specific URL and extracts its visible text content."""
    res = await visit_page(url, max_chars)
    return res

@mcp.tool()
async def fetch_and_encode_image_tool(url: str) -> str:
    """Internal research tool to fetch and base64 encode an image URL."""
    res = await fetch_and_encode_image(url)
    return res


# Create the app instance and add middleware
app = mcp.sse_app()
app.add_middleware(AuthMiddleware)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)