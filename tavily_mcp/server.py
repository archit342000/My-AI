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

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
import uvicorn
from starlette.responses import JSONResponse

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tavily_mcp_server")

def sanitize_output(text: str) -> str:
    """Basic output sanitization to prevent injection."""
    if not isinstance(text, str):
        return text
    # Strip remaining raw HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    # Strip suspicious URIs
    text = re.sub(r'(?i)(javascript|vbscript|data):', '', text)
    # Strip obvious script-like structures if any leaked through
    text = re.sub(r'(?i)eval\(|document\.cookie|window\.', '', text)
    return text

def get_secret(secret_name, default=None):
    try:
        with open(f"/run/secrets/{secret_name}", "r") as f:
            return f.read().strip()
    except IOError:
        return os.getenv(secret_name, default)

TAVILY_BASE_URL = "https://api.tavily.com"
TAVILY_API_KEY = get_secret("TAVILY_API_KEY", "")
MCP_API_KEY = get_secret("MCP_API_KEY", "")

# Constants
TIMEOUT_TAVILY_SEARCH_ASYNC = 20.0
TIMEOUT_TAVILY_MAP = 30.0

SEARCH_DEPTH = "advanced"
INCLUDE_ANSWER = True
INCLUDE_RAW_CONTENT = True
MAX_SEARCH_RESULTS = 10
MIN_SEARCH_RESULTS = 3
RELEVANCE_THRESHOLD = 0.5
SEARCH_CACHE_TTL = 3600

_tavily_search_cache = {}

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
                raw = res.get("raw_content") or "No raw content available."

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
                    "raw_content": sanitize_output(raw_output),
                    "timestamp": time.time()
                }

            return json.dumps({
                "standard_output": sanitize_output(standard_output),
                "raw_output": sanitize_output(raw_output),
                "images": images,
                "results": [
                    {k: sanitize_output(str(v)) if isinstance(v, str) else v for k, v in r.items()}
                    for r in filtered_results
                ]
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

    return sanitize_output(cache_entry["raw_content"])

async def async_tavily_search(query: str, topic: str = "general", time_range: str | None = None,
                              start_date: str | None = None, end_date: str | None = None, max_results: int = 10):
    url = f"{TAVILY_BASE_URL}/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",
        "topic": topic if topic in ["general", "news"] else "general",
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
                 "results": [
                     {k: sanitize_output(str(v)) if isinstance(v, str) else v for k, v in r.items()}
                     for r in data.get("results", [])
                 ],
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
        "max_depth": 3,
        "max_breadth": 10,
        "limit": 10,
        "allow_external": True,
        "exclude_paths": ["/login", "/signup", "/auth"],
        "exclude_domains": ["facebook.com", "twitter.com", "instagram.com"]
    }
    async with httpx.AsyncClient(timeout=TIMEOUT_TAVILY_MAP) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            return json.dumps({
                "results": [
                     {k: sanitize_output(str(v)) if isinstance(v, str) else v for k, v in r.items()}
                     for r in results
                 ]
            })
        except Exception as e:
            return json.dumps({"error": str(e), "results": []})

# =====================================================================
# MCP SERVER SETUP (FastMCP)
# =====================================================================

mcp = FastMCP("tavily_tools_mcp", host="0.0.0.0", port=8000)

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

# Create the app instance and add middleware
app = mcp.sse_app()
app.add_middleware(AuthMiddleware)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
