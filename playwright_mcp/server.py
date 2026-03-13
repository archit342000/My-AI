import asyncio
import os
import json
import logging
import base64
import random
import re
import urllib.parse
from urllib.parse import urlparse, urljoin
import socket
import ipaddress
import io

import httpx
from selectolax.lexbor import LexborHTMLParser
import pypdf
from playwright.async_api import async_playwright

from mcp.server.fastmcp import FastMCP
import uvicorn
from starlette.responses import JSONResponse

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("playwright_mcp_server")

# =====================================================================
def get_secret(secret_name, default=None):
    try:
        with open(f"/run/secrets/{secret_name}", "r") as f:
            return f.read().strip()
    except IOError:
        return os.getenv(secret_name, default)

MCP_API_KEY = get_secret("PLAYWRIGHT_MCP_API_KEY", "")

# Constants
TIMEOUT_WEB_SCRAPE = 15.0
TIMEOUT_IMAGE_FETCH = 10.0
URL_FETCH_RETRIES = 3
RESEARCH_IMAGE_FETCH_RETRIES = 3

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0"
]

# =====================================================================
# SSRF / Security and Utility Functions
# =====================================================================

def is_safe_web_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if not parsed.hostname:
            return False
        ip = socket.gethostbyname(parsed.hostname)
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast:
            return False
        return True
    except Exception:
        return False

async def _extract_pdf_content(pdf_bytes: bytes) -> str:
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return ""

def clean_html_to_markdown(html_content, base_url, detail_level="standard"):
    """Strips noise from HTML and converts to clean markdown based on detail_level."""
    try:
        parser = LexborHTMLParser(html_content)

        if detail_level == "basic":
            # Aggressive cleanup for basic reading
            noise_selectors = [
                "script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "meta",
                "iframe", "ins.adsbygoogle", ".ad", ".advertisement", ".banner"
            ]
        elif detail_level == "deep":
            # Minimal cleanup for high-fidelity dashboards
            noise_selectors = ["script", "style", "meta", "iframe"]
        else: # standard
            # Balanced cleanup
            noise_selectors = [
                "script", "style", "noscript", "meta",
                "iframe", "ins.adsbygoogle", ".ad", ".advertisement", ".banner"
            ]

        for selector in noise_selectors:
            for node in parser.css(selector):
                node.decompose()

        # Selection Strategy
        if detail_level == "basic":
            # Semantic heuristic for articles
            content_node = None
            for wrapper in ["article", "main", ".main-content", ".post-body"]:
                matches = parser.css(wrapper)
                if matches:
                    content_node = matches[0]
                    break
            if not content_node:
                content_node = parser.body if parser.body else parser.root
        else:
            # Full body for data-heavy sites
            content_node = parser.body if parser.body else parser.root

        import markdownify
        
        # Stripping Strategy
        if detail_level == "basic":
            strip_tags = ["img", "a", "script", "style", "table"]
        else:
            strip_tags = ["img", "script", "style"] # Keep 'a' and 'table'

        if not content_node:
            return ""

        md_text = markdownify.markdownify(
            content_node.html,
            heading_style="ATX",
            strip=strip_tags
        )

        md_text = re.sub(r'\n[ \t]+', '\n', md_text)
        md_text = re.sub(r'[ \t]+$', '', md_text, flags=re.MULTILINE)
        md_text = re.sub(r'([*_=]){4,}', r'\1\1\1', md_text)
        md_text = re.sub(r'\n{3,}', '\n\n', md_text)
        return md_text.strip()
    except Exception as e:
        logger.error(f"HTML to Markdown error: {e}")
        return ""

def sanitize_output(text: str) -> str:
    """Basic output sanitization to prevent injection."""
    # Strip remaining raw HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    # Strip suspicious URIs
    text = re.sub(r'(?i)(javascript|vbscript|data):', '', text)
    # Strip obvious script-like structures if any leaked through
    text = re.sub(r'(?i)eval\(|document\.cookie|window\.', '', text)
    return text

async def check_internet_connectivity():
    """Ping a reliable host to check for general internet connectivity."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.get("https://1.1.1.1")
            return True
    except Exception:
        return False

# =====================================================================
# Playwright & Fetching Logic
# =====================================================================

async def fetch_with_playwright(url: str, max_chars: int = 40000, detail_level: str = "standard") -> str:
    """Site visit using Playwright with level-specific strategies."""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            page = await browser.new_page(
                user_agent=random.choice(USER_AGENTS),
                viewport={'width': 1920, 'height': 1080}
            )

            # Navigation Strategy
            wait_until = "load" if detail_level == "basic" else "domcontentloaded"
            logger.info(f"Navigating to {url} (level: {detail_level})...")
            response = await page.goto(url, timeout=TIMEOUT_WEB_SCRAPE * 1000, wait_until=wait_until)

            if not response:
                await browser.close()
                return "Error: Playwright could not load the page."

            # Overlay Hiding Strategy
            if detail_level != "basic":
                await page.add_style_tag(content="""
                    #onetrust-banner-sdk, .cookie-consent, .consent-banner, .modal, .popup, [class*='cookie'], [id*='cookie'] { 
                        display: none !important; 
                    }
                """)

            # Interaction Strategy
            if detail_level != "basic":
                scroll_limit = 10000 if detail_level == "deep" else 5000
                logger.info(f"Scrolling (limit: {scroll_limit})...")
                await page.evaluate(f"""
                    async () => {{
                        await new Promise((resolve) => {{
                            let totalHeight = 0;
                            let distance = 200;
                            let timer = setInterval(() => {{
                                let scrollHeight = document.body.scrollHeight;
                                window.scrollBy(0, distance);
                                totalHeight += distance;
                                if(totalHeight >= scrollHeight || totalHeight > {scroll_limit}){{
                                    clearInterval(timer);
                                    window.scrollTo(0, 0);
                                    resolve();
                                }}
                            }}, 100);
                        }});
                    }}
                """)

            # Settle period Strategy
            if detail_level == "deep":
                await asyncio.sleep(5)
            elif detail_level == "standard":
                await asyncio.sleep(2)

            # Extract raw HTML
            html_content = await page.content()
            await browser.close()

            text = clean_html_to_markdown(html_content, url, detail_level)
            if not text:
                 return "Error: Playwright visited the page but could not find any valid text content."

            return text[:max_chars]
    except Exception as e:
        logger.error(f"Playwright error: {str(e)}")
        return f"Error visiting page with Playwright: {str(e)}"


async def visit_page(url: str, max_chars: int = 40000, detail_level: str = "standard"):
    if not is_safe_web_url(url):
        return "Error: URL is forbidden (SSRF protection). Cannot visit local or private IP addresses."

    logger.info(f"Pure Playwright Visit: {url} (level: {detail_level})")
    
    # Check internet connectivity
    is_connected = await check_internet_connectivity()
    if not is_connected:
        return "Error: Could not visit page due to general internet connectivity failure on the server."

    # Execute extraction
    extracted_text = await fetch_with_playwright(url, max_chars, detail_level)
    
    final_text = extracted_text[:max_chars]
    return sanitize_output(final_text)

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

mcp = FastMCP("playwright_tools_mcp", host="0.0.0.0", port=8001)

class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        if path in ["/sse", "/messages/"] or path.startswith("/messages/"):
            if MCP_API_KEY:
                headers = dict(scope.get("headers", []))
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
async def visit_page_tool(url: str, max_chars: int = 40000, detail_level: str = "standard") -> str:
    """Visits a specific URL and extracts its visible text content using a headless browser. Levels: basic, standard, deep."""
    res = await visit_page(url, max_chars, detail_level)
    return res

@mcp.tool()
async def fetch_and_encode_image_tool(url: str) -> str:
    """Internal research tool to fetch and base64 encode an image URL."""
    res = await fetch_and_encode_image(url)
    return res

app = mcp.sse_app()
app.add_middleware(AuthMiddleware)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
