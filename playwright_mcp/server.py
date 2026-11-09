import asyncio
import hashlib
import hmac
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
import time
from typing import Dict, Any, List, Optional

import httpx
from selectolax.lexbor import LexborHTMLParser
import pypdf
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

from mcp.server.fastmcp import FastMCP
import uvicorn
from starlette.responses import JSONResponse, Response
from starlette.requests import Request

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

# Per-step timeouts for visit_page (seconds)
TIMEOUT_BROWSER_LAUNCH = 30       # Max time to launch a new browser context
TIMEOUT_SCROLL_EVALUATE = 60      # Max time for the scroll JS to resolve
TIMEOUT_PAGE_CONTENT = 15         # Max time for page.content() extraction
TIMEOUT_VISIT_PAGE_OVERALL = 180  # Hard cap on the entire visit_page operation

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0"
]

# =====================================================================
# Session Management for Browsing Agent
# =====================================================================

_playwright_manager = None
_playwright_instance = None
_playwright_lock = asyncio.Lock()

_portal_process = None
_portal_cdp_port = 9222
_portal_user_data_dir = os.path.join(os.getcwd(), "playwright_data", "portal_profile")

async def _get_playwright():
    global _playwright_manager, _playwright_instance
    async with _playwright_lock:
        if _playwright_instance is None:
            # Automated update check: Ensure browser binaries match library version
            try:
                import subprocess
                logger.info("Verifying browser binaries...")
                def _install():
                    subprocess.run(["playwright", "install", "chromium"], check=True, capture_output=True)
                await asyncio.to_thread(_install)
            except Exception as e:
                logger.warning(f"Could not automatically update browser binaries: {e}")

            manager = async_playwright()
            try:
                _playwright_instance = await manager.start()
                _playwright_manager = manager
            except Exception:
                logger.error("Failed to start Playwright manager")
                raise
    return _playwright_instance

_sessions: Dict[str, dict] = {}
SESSION_TIMEOUT = 300  # 5 minutes auto-cleanup

async def _cleanup_expired_sessions():
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["last_used"] > SESSION_TIMEOUT]
    for sid in expired:
        try:
            if "browser_cdp" in _sessions[sid]:
                await _sessions[sid]["browser_cdp"].close()
            else:
                await _sessions[sid]["context"].close()
        except Exception as e:
            logger.error(f"Error closing expired session {sid}: {e}")
        del _sessions[sid]

async def _get_session(session_id: str):
    await _cleanup_expired_sessions()
    if session_id not in _sessions:
        raise ValueError("Session not found or expired")
    
    session = _sessions[session_id]
    page = session.get("page")
    browser_cdp = session.get("browser_cdp")
    
    if (page and page.is_closed()) or (browser_cdp and not browser_cdp.is_connected()):
        logger.warning(f"Session {session_id} is dead (page closed or browser disconnected). Cleaning up...")
        try:
            if "browser_cdp" in session:
                await session["browser_cdp"].close()
            else:
                await session["context"].close()
        except Exception:
            pass
        del _sessions[session_id]
        raise ValueError("Session is no longer active (browser closed or disconnected)")
        
    session["last_used"] = time.time()
    return session

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
            noise_selectors = ["script", "style", "meta", "iframe", "svg"]
        else: # standard
            # Balanced cleanup
            noise_selectors = [
                "script", "style", "noscript", "meta", "svg",
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
            strip_tags = ["script", "style"] # Keep 'a', 'table', and 'img' (for alt-text)

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
        
        # Strip out massive base64 image data strings to prevent context window overflow
        md_text = re.sub(r'data:image/[^;]+;base64,[a-zA-Z0-9+/=\s]+', '[Base64 Image Omitted]', md_text)
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
    """Site visit using Playwright with level-specific strategies.
    
    Reuses the shared Playwright instance to avoid spawning a new subprocess
    per call. Each invocation gets its own ephemeral browser context that is
    always closed on exit.
    """
    browser = None
    try:
        p = await _get_playwright()
        browser = await asyncio.wait_for(
            p.chromium.launch(
                headless=True, 
                args=[
                    '--no-sandbox', 
                    '--disable-setuid-sandbox',
                    '--disable-background-networking',
                    '--disable-client-side-phishing-detection'
                ]
            ),
            timeout=TIMEOUT_BROWSER_LAUNCH
        )
        page = await browser.new_page(
            user_agent=random.choice(USER_AGENTS),
            viewport={'width': 1920, 'height': 1080}
        )
        await stealth_async(page)

        async def abort_unnecessary_requests(route):
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                await route.abort()
            else:
                await route.continue_()
        await page.route("**/*", abort_unnecessary_requests)

        # Navigation Strategy
        wait_until = "load" if detail_level == "basic" else "domcontentloaded"
        logger.info(f"Navigating to {url} (level: {detail_level})...")
        response = await page.goto(url, timeout=TIMEOUT_WEB_SCRAPE * 1000, wait_until=wait_until)

        if not response:
            return "Error: Playwright could not load the page."

        # Overlay Hiding Strategy
        if detail_level != "basic":
            try:
                await asyncio.wait_for(
                    page.add_style_tag(content="""
                        #onetrust-banner-sdk, .cookie-consent, .consent-banner, .modal, .popup, [class*='cookie'], [id*='cookie'] { 
                            display: none !important; 
                        }
                    """),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"add_style_tag timed out for {url} (likely due to CSP sandbox), proceeding without it")
            except Exception as e:
                logger.warning(f"add_style_tag failed for {url}: {e}")

        # Interaction Strategy — with timeout to prevent infinite scroll hangs
        if detail_level != "basic":
            scroll_limit = 10000 if detail_level == "deep" else 5000
            logger.info(f"Scrolling (limit: {scroll_limit})...")
            try:
                await asyncio.wait_for(
                    page.evaluate(f"""
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
                    """),
                    timeout=TIMEOUT_SCROLL_EVALUATE
                )
            except asyncio.TimeoutError:
                logger.warning(f"Scroll evaluate timed out after {TIMEOUT_SCROLL_EVALUATE}s for {url}, proceeding with partial content")

        # Settle period Strategy
        if detail_level == "deep":
            await asyncio.sleep(5)
        elif detail_level == "standard":
            await asyncio.sleep(2)

        # Extract raw HTML — with timeout
        try:
            html_content = await asyncio.wait_for(
                page.content(),
                timeout=TIMEOUT_PAGE_CONTENT
            )
        except asyncio.TimeoutError:
            logger.warning(f"page.content() timed out after {TIMEOUT_PAGE_CONTENT}s for {url}")
            return "Error: Timed out extracting page content."

        text = clean_html_to_markdown(html_content, url, detail_level)
        if not text:
             return "Error: Playwright visited the page but could not find any valid text content."

        return text[:max_chars]
    except asyncio.TimeoutError:
        logger.error(f"Playwright operation timed out for {url}")
        return f"Error: Playwright timed out while processing {url}"
    except Exception as e:
        logger.error(f"Playwright error: {str(e)}")
        return f"Error visiting page with Playwright: {str(e)}"
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass


async def visit_page(url: str, max_chars: int = 40000, detail_level: str = "standard"):
    if not is_safe_web_url(url):
        return "Error: URL is forbidden (SSRF protection). Cannot visit local or private IP addresses."

    logger.info(f"Pure Playwright Visit: {url} (level: {detail_level})")
    
    # Check internet connectivity
    is_connected = await check_internet_connectivity()
    if not is_connected:
        return "Error: Could not visit page due to general internet connectivity failure on the server."

    # Execute extraction with an overall hard timeout as a safety net
    try:
        extracted_text = await asyncio.wait_for(
            fetch_with_playwright(url, max_chars, detail_level),
            timeout=TIMEOUT_VISIT_PAGE_OVERALL
        )
    except asyncio.TimeoutError:
        logger.error(f"visit_page overall timeout ({TIMEOUT_VISIT_PAGE_OVERALL}s) exceeded for {url}")
        return f"Error: Page visit timed out after {TIMEOUT_VISIT_PAGE_OVERALL}s."
    
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

            if not resp or resp.status_code in (301, 302, 303, 307, 308):
                return json.dumps({"error": "Failed to fetch image (redirect loop or no image found)"})
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
        """Requires the `X-MCP-API-KEY` header on the MCP routes (`/sse`, `/messages/...`) and the browser
        portal routes (`/portal/...`).

        Fails closed: when `PLAYWRIGHT_MCP_API_KEY` is not configured the protected routes are rejected with
        401, as are missing, repeated or wrong keys. Other paths and non-HTTP scopes pass through. The key
        is compared as fixed-length digests with `hmac.compare_digest` and is never logged.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        if path == "/sse" or path.startswith(("/messages/", "/portal/")):
            sent = [value for name, value in scope.get("headers", []) if name == b"x-mcp-api-key"]
            if not MCP_API_KEY:
                reason = "PLAYWRIGHT_MCP_API_KEY is not configured"
            elif len(sent) != 1:
                reason = "missing or repeated key header"
            elif not hmac.compare_digest(hashlib.sha256(sent[0]).digest(),
                                         hashlib.sha256(MCP_API_KEY.encode("utf-8")).digest()):
                reason = "wrong key"
            else:
                reason = None
            if reason:
                logger.warning(f"Unauthorized access attempt to {path!r}: {reason}")
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

# --- Browsing Agent Tools ---

@mcp.tool()
async def browser_start_session(session_id: str, stealth_level: str = "minimal", scope: Optional[List[str]] = None) -> str:
    """Creates or joins a persistent browser session. Stealth levels: minimal, advanced."""
    global _sessions
    await _cleanup_expired_sessions()
    if session_id in _sessions:
        # Update scope if provided even for existing session
        if scope is not None:
            _sessions[session_id]["scope"] = scope
        return json.dumps({"status": "exists", "session_id": session_id})
    
    try:
        p = await _get_playwright()
        
        # If the portal Chromium is running, connect to it via CDP
        if _portal_process and _portal_process.poll() is None:
            logger.info("Connecting to portal Chromium via CDP...")
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{_portal_cdp_port}")
            context = browser.contexts[0] if browser.contexts else browser.contexts[0] # Actually we should get the context
            
            # Use existing context, create page if none
            context = browser.contexts[0]
            if context.pages:
                page = context.pages[0]
            else:
                page = await context.new_page()

            _sessions[session_id] = {
                "context": context,
                "page": page,
                "browser_cdp": browser,
                "stealth_level": stealth_level,
                "scope": scope,
                "last_used": time.time()
            }
            return json.dumps({"status": "connected_cdp", "session_id": session_id, "stealth_level": stealth_level})
        
        # Fallback: launch standalone Playwright context
        user_data_dir = os.path.join(os.getcwd(), "playwright_data", "default_profile")
        os.makedirs(user_data_dir, exist_ok=True)

        # In persistent mode, we launch the context directly. 
        # Note: If another instance is already using this dir, it will raise an error.
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            user_agent=random.choice(USER_AGENTS),
            viewport={'width': 1920, 'height': 1080},
            locale="en-US",
            timezone_id="America/New_York",
            env={**os.environ, "DISPLAY": ":99"},
            args=[
                '--no-sandbox', 
                '--disable-setuid-sandbox', 
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--window-size=1920,1080',
                '--disable-background-networking',
                '--disable-client-side-phishing-detection'
            ]
        )
        
        # Extended initialization script for Deep Stealth
        stealth_init_script = """
            // 1. Scrub CDP/ChromeDriver leaks (cdc_)
            for (const key in window) {
                if (key.startsWith('cdc_')) {
                    delete window[key];
                }
            }
            // 2. Hide navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            // 3. Spoof WebGL vendor and renderer
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Google Inc. (Intel)';
                if (parameter === 37446) return 'ANGLE (Intel, Intel(R) Iris(TM) Plus Graphics 640, OpenGL 4.1)';
                return getParameter.apply(this, [parameter]);
            };
            // 4. Spoof hardware concurrency and memory
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
            Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
        """
        await context.add_init_script(stealth_init_script)
        
        # Persistent context starts with an initial page
        if context.pages:
            page = context.pages[0]
        else:
            page = await context.new_page()
            
        await stealth_async(page)
        
        _sessions[session_id] = {
            "context": context,
            "page": page,
            "stealth_level": stealth_level,
            "scope": scope,
            "last_used": time.time()
        }
        return json.dumps({"status": "created", "session_id": session_id, "stealth_level": stealth_level})
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
async def browser_end_session(session_id: str) -> str:
    """Closes the persistent browser context and cleans up session state."""
    global _sessions
    if session_id in _sessions:
        try:
            if "browser_cdp" in _sessions[session_id]:
                await _sessions[session_id]["browser_cdp"].close()
            else:
                await _sessions[session_id]["context"].close()
        except Exception:
            pass
        del _sessions[session_id]
        return json.dumps({"status": "closed"})
    return json.dumps({"status": "not_found"})

@mcp.tool()
async def browser_navigate(session_id: str, url: str) -> str:
    """Navigates the session's page to a URL."""
    if not is_safe_web_url(url):
         return json.dumps({"error": "Forbidden URL (SSRF protection)"})
    try:
        s = await _get_session(session_id)
        
        # Scope Enforcement
        scope = s.get("scope")
        if scope:
            parsed = urlparse(url)
            domain = parsed.hostname
            if domain:
                domain = domain.lower()
                # Check if domain matches any in scope (exact or subdomain)
                is_allowed = False
                for s_domain in scope:
                    s_domain = s_domain.lower()
                    if domain == s_domain or domain.endswith('.' + s_domain):
                        is_allowed = True
                        break
                
                if not is_allowed:
                    return json.dumps({"error": f"Navigation blocked. Domain '{domain}' is not in the allowed scope: {scope}. You may only navigate directly to these domains, but you are free to CLICK on links within pages to go elsewhere."})

        page = s["page"]
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        return json.dumps({"status": "ok", "url": page.url, "title": await page.title()})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def browser_read_page(session_id: str) -> str:
    """Extracts visible text content from the page, converted to markdown."""
    try:
        s = await _get_session(session_id)
        page = s["page"]
        html_content = await page.content()
        url = page.url
        text = clean_html_to_markdown(html_content, url, "standard")
        return sanitize_output(text[:40000])
    except Exception as e:
        logger.error(f"Error reading page: {e}")
        return json.dumps({"error": str(e)})

@mcp.tool()
async def browser_click(session_id: str, selector: str) -> str:
    """Clicks an element by CSS selector."""
    try:
        s = await _get_session(session_id)
        page = s["page"]
        if s.get("stealth_level") == "advanced":
            # Human-like reaction delay
            await asyncio.sleep(random.uniform(0.3, 0.8))
            
            # Retrieve element and its bounding box to simulate mouse movement
            element = await page.wait_for_selector(selector, timeout=5000)
            box = await element.bounding_box()
            if box:
                # Target a randomized point within the bounding box
                target_x = box['x'] + box['width'] * random.uniform(0.2, 0.8)
                target_y = box['y'] + box['height'] * random.uniform(0.2, 0.8)
                
                # Move mouse in 'steps' to simulate a path rather than a jump
                await page.mouse.move(target_x, target_y, steps=random.randint(10, 20))
                await asyncio.sleep(random.uniform(0.1, 0.2))
            
            await page.click(selector)
            await asyncio.sleep(random.uniform(0.2, 0.5))
        else:
            await page.click(selector)
            
        return json.dumps({"status": "clicked", "selector": selector})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def browser_type(session_id: str, selector: str, text: str, submit: bool = False) -> str:
    """Types text into an input, optionally presses Enter."""
    try:
        s = await _get_session(session_id)
        if s.get("stealth_level") == "advanced":
            # Simulate 'finding' the input field and deciding to type
            await asyncio.sleep(random.uniform(0.4, 1.2))
            await s["page"].type(selector, text, delay=random.randint(60, 200))
        else:
            await s["page"].fill(selector, text)
            
        if submit:
            if s.get("stealth_level") == "advanced":
                await asyncio.sleep(random.uniform(0.3, 0.6))
            await s["page"].press(selector, "Enter")
        return json.dumps({"status": "typed", "selector": selector, "submitted": submit})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def browser_scroll(session_id: str, direction: str, amount: int = 500) -> str:
    """Scrolls the page up or down. Direction can be 'up' or 'down'."""
    try:
        s = await _get_session(session_id)
        page = s["page"]
        dy = amount if direction.lower() == "down" else -amount
        
        if s.get("stealth_level") == "advanced":
            # Break large scroll into human-like segments
            steps = random.randint(3, 6)
            step_amount = dy / steps
            for _ in range(steps):
                await page.mouse.wheel(0, step_amount)
                await asyncio.sleep(random.uniform(0.05, 0.2))
            await asyncio.sleep(random.uniform(0.2, 0.4))
        else:
            await page.mouse.wheel(0, dy)
            
        return json.dumps({"status": "scrolled", "direction": direction, "amount": dy})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def browser_get_interactive_elements(session_id: str) -> str:
    """Returns a structured list of clickable/typeable elements."""
    try:
        s = await _get_session(session_id)
        page = s["page"]
        elements = await page.evaluate('''
            () => {
                const results = [];
                const interactables = document.querySelectorAll('a, button, input, select, textarea, [role="button"], [tabindex]');
                interactables.forEach((el, index) => {
                    const rect = el.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden';
                    if(isVisible) {
                        let selector = el.id ? '#' + CSS.escape(el.id) : '';
                        if (!selector) {
                            const classes = el.getAttribute('class');
                            if (classes) {
                                selector = el.tagName.toLowerCase() + '.' + classes.trim().split(/\\s+/).map(c => CSS.escape(c)).join('.');
                            } else {
                                selector = el.tagName.toLowerCase();
                                if (el.getAttribute('name')) selector += `[name="${CSS.escape(el.getAttribute('name'))}"]`;
                            }
                        }
                        results.push({
                            selector: selector,
                            tag: el.tagName.toLowerCase(),
                            text: (el.innerText || el.value || el.placeholder || '').trim().substring(0, 100),
                            type: el.type || '',
                            href: el.getAttribute('href') || ''
                        });
                    }
                });
                const unique = [];
                const seen = new Set();
                results.forEach(r => {
                    const key = r.text + '|' + r.href;
                    if (!seen.has(key) && (r.text || r.href || r.type)) {
                        seen.add(key);
                        unique.push(r);
                    }
                });
                return unique.slice(0, 100);
            }
        ''')
        return json.dumps(elements)
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def browser_back(session_id: str) -> str:
    """Navigates back to the previous page in history."""
    try:
        s = await _get_session(session_id)
        await s["page"].go_back()
        return json.dumps({"status": "navigated_back", "url": s["page"].url})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
async def browser_screenshot(session_id: str) -> str:
    """Takes a viewport screenshot, returns base64-encoded JPEG (compressed)."""
    try:
        s = await _get_session(session_id)
        screenshot_bytes = await s["page"].screenshot(full_page=False, type="jpeg", quality=60)
        b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        return json.dumps({"image": f"data:image/jpeg;base64,{b64}"})
    except Exception as e:
        return json.dumps({"error": str(e)})

# =====================================================================
# Portal Endpoints (FastAPI/Starlette)
# =====================================================================

portal_session_id = "portal_global_session"

import subprocess
import shutil

@mcp.custom_route("/portal/init", methods=["POST"])
async def portal_init(request: Request):
    """Initializes the browser session for the portal using a standalone Chromium process."""
    global _portal_process
    try:
        if _portal_process and _portal_process.poll() is None:
            logger.info("Reusing existing standalone portal session.")
            return JSONResponse({"status": "reused"})
            
        logger.info("Initializing new standalone portal session...")
        os.makedirs(_portal_user_data_dir, exist_ok=True)
        
        # Dynamically fetch the correct Chromium executable path from Playwright
        p = await _get_playwright()
        chromium_path = p.chromium.executable_path
        
        _portal_process = subprocess.Popen([
            chromium_path,
            f"--remote-debugging-port={_portal_cdp_port}",
            f"--user-data-dir={_portal_user_data_dir}",
            "--no-sandbox", 
            "--disable-setuid-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage", # Fixes 'No space left on device' (shm exhaustion)
            "--window-size=1920,1080",
            "--no-first-run", 
            "--disable-default-apps",
            "--disable-background-networking",
            "--disable-client-side-phishing-detection",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "https://www.google.com"
        ], env={**os.environ, "DISPLAY": ":99"})
        
        return JSONResponse({"status": "created"})
    except Exception as e:
        logger.error(f"Portal init error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)

app = mcp.sse_app()
app.add_middleware(AuthMiddleware)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Playwright MCP server...")
    
    # 1. Terminate portal process if running
    global _portal_process
    if _portal_process:
        try:
            logger.info("Terminating portal process...")
            _portal_process.terminate()
            # Wait up to 5 seconds, then kill if not dead
            for _ in range(50):
                if _portal_process.poll() is not None:
                    break
                await asyncio.sleep(0.1)
            else:
                logger.warning("Portal process did not terminate, killing...")
                _portal_process.kill()
        except Exception as e:
            logger.error(f"Error terminating portal process: {e}")
        _portal_process = None

    # 2. Close all active sessions
    global _sessions
    for sid in list(_sessions.keys()):
        try:
            session = _sessions[sid]
            logger.info(f"Closing active session {sid}...")
            if "browser_cdp" in session:
                await session["browser_cdp"].close()
            else:
                await session["context"].close()
        except Exception as e:
            logger.error(f"Error closing session {sid} during shutdown: {e}")
    _sessions.clear()

    # 3. Stop playwright instance
    global _playwright_instance, _playwright_manager
    async with _playwright_lock:
        if _playwright_instance:
            try:
                logger.info("Stopping Playwright manager...")
                await _playwright_manager.stop()
            except Exception as e:
                logger.error(f"Error stopping Playwright manager: {e}")
            _playwright_instance = None
            _playwright_manager = None

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
