from backend.logging import error_detail, log_event
from backend.mcp_client import playwright_client
from backend.database import db

async def _get_session_id(chat_id: str) -> str:
    try:
        chat_meta = db.get_chat(chat_id)
        if not chat_meta:
            raise ValueError("No active browsing session found for this chat.")
        session_id = chat_meta.get("browsing_session_id")
        if not session_id:
            raise ValueError("No active browsing session found for this chat.")
        return session_id
    except Exception as e:
        if isinstance(e, ValueError):
            raise e
        import logging
        logging.getLogger(__name__).error(f"Database error in _get_session_id: {e}")
        raise ValueError("No active browsing session found for this chat.")

async def browser_navigate(url: str, chat_id: str, **kwargs) -> str:
    session_id = await _get_session_id(chat_id)
    await playwright_client.connect()
    res = await playwright_client.execute_tool("browser_navigate", {"session_id": session_id, "url": url})
    return res.content[0].text if res.content else "{}"

async def browser_read_page(chat_id: str, **kwargs) -> str:
    session_id = await _get_session_id(chat_id)
    await playwright_client.connect()
    res = await playwright_client.execute_tool("browser_read_page", {"session_id": session_id})
    text = res.content[0].text if res.content else "{}"
    
    from backend.config import BROWSING_AGENT_MAX_CHARS_PER_PAGE
    if len(text) > BROWSING_AGENT_MAX_CHARS_PER_PAGE:
        text = text[:BROWSING_AGENT_MAX_CHARS_PER_PAGE] + "\n\n[Truncated — use browser_scroll and browser_read_page again for more content]"
    return text

async def browser_click(selector: str, chat_id: str, **kwargs) -> str:
    session_id = await _get_session_id(chat_id)
    await playwright_client.connect()
    res = await playwright_client.execute_tool("browser_click", {"session_id": session_id, "selector": selector})
    return res.content[0].text if res.content else "{}"

async def browser_type(selector: str, text: str, chat_id: str, submit: bool = False, **kwargs) -> str:
    session_id = await _get_session_id(chat_id)
    await playwright_client.connect()
    res = await playwright_client.execute_tool("browser_type", {"session_id": session_id, "selector": selector, "text": text, "submit": submit})
    return res.content[0].text if res.content else "{}"

async def browser_scroll(direction: str, chat_id: str, amount: int = 500, **kwargs) -> str:
    session_id = await _get_session_id(chat_id)
    await playwright_client.connect()
    res = await playwright_client.execute_tool("browser_scroll", {"session_id": session_id, "direction": direction, "amount": amount})
    return res.content[0].text if res.content else "{}"

async def browser_get_interactive_elements(chat_id: str, **kwargs) -> str:
    session_id = await _get_session_id(chat_id)
    await playwright_client.connect()
    res = await playwright_client.execute_tool("browser_get_interactive_elements", {"session_id": session_id})
    text = res.content[0].text if res.content else "{}"
    
    from backend.config import BROWSING_AGENT_MAX_CHARS_INTERACTIVE
    if len(text) > BROWSING_AGENT_MAX_CHARS_INTERACTIVE:
        text = text[:BROWSING_AGENT_MAX_CHARS_INTERACTIVE] + "\n\n[Truncated — use browser_scroll to reach more elements]"
    return text

async def browser_back(chat_id: str, **kwargs) -> str:
    session_id = await _get_session_id(chat_id)
    await playwright_client.connect()
    res = await playwright_client.execute_tool("browser_back", {"session_id": session_id})
    return res.content[0].text if res.content else "{}"

async def browser_screenshot(chat_id: str, **kwargs) -> str:
    import os
    import json
    import base64
    from backend.config import DATA_DIR
    from datetime import datetime
    
    session_id = await _get_session_id(chat_id)
    await playwright_client.connect()
    res = await playwright_client.execute_tool("browser_screenshot", {"session_id": session_id})
    
    if not res.content:
        return "{}"
    
    try:
        data = json.loads(res.content[0].text)
        if "image" in data and data["image"].startswith("data:image"):
            # Extract base64
            header, encoded = data["image"].split(",", 1)
            img_bytes = base64.b64decode(encoded)
            
            # Save to disk
            screenshot_dir = os.path.join(DATA_DIR, "screenshots", chat_id)
            os.makedirs(screenshot_dir, exist_ok=True)
            
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            filepath = os.path.join(screenshot_dir, filename)
            
            with open(filepath, "wb") as f:
                f.write(img_bytes)
            
            # Return a reference that InferenceEngine can recognize
            return json.dumps({
                "status": "success",
                "message": "Screenshot captured and saved to disk.",
                "screenshot_ref": filepath,
                "mime_type": "image/jpeg"
            })
        return res.content[0].text
    except Exception as e:
        log_event("browser_screenshot_error", {"error": error_detail(e)})
        return json.dumps({"error": "Could not process the screenshot. Try again."})
