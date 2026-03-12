import asyncio
import os
import json
import logging
import base64
import time
from typing import Optional

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse
import uvicorn
import websockets

from .agent import run_browser_task, active_tasks, add_interrupt_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("browser_mcp_server")

def get_secret(secret_name, default=None):
    try:
        with open(f"/run/secrets/{secret_name}", "r") as f:
            return f.read().strip()
    except IOError:
        return os.getenv(secret_name, default)

MCP_API_KEY = get_secret("MCP_API_KEY", "")

mcp = FastMCP("browser_mcp", host="0.0.0.0", port=8000)

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

        # Handle custom interrupt endpoint on the MCP server directly
        if path == "/interrupt" and scope["method"] == "POST":
            # Simplified interrupt handler logic here (though we could also do it via websocket)
            # We'll stick to a simple endpoint
            from starlette.requests import Request
            request = Request(scope, receive)
            try:
                data = await request.json()
                task_id = data.get("task_id")
                message = data.get("message", "User interrupted the operation.")
                if task_id in active_tasks:
                    add_interrupt_message(task_id, message)
                    res = JSONResponse({"status": "Interrupted", "message": message})
                else:
                    res = JSONResponse({"error": "Task not found"}, status_code=404)
                await res(scope, receive, send)
                return
            except Exception as e:
                res = JSONResponse({"error": str(e)}, status_code=400)
                await res(scope, receive, send)
                return

        await self.app(scope, receive, send)

@mcp.tool()
async def start_browsing_task(goal: str, mode: str = "automatic", task_id: str = "default") -> str:
    """
    Executes a web browsing task autonomously using Playwright.
    The mode can be 'automatic' (it completes the task and returns the result)
    or 'semi-automatic' (it may pause and ask for user input).
    """
    logger.info(f"Starting browsing task: {goal} in {mode} mode")
    try:
        result = await run_browser_task(task_id, goal, mode)
        return json.dumps({"status": "success", "result": result})
    except Exception as e:
        logger.error(f"Error in start_browsing_task: {e}")
        return json.dumps({"status": "error", "error": str(e)})

app = mcp.sse_app()
app.add_middleware(AuthMiddleware)

async def start_mcp_server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

# WebSocket Server for Streaming Screenshots
connected_clients = set()

async def ws_handler(websocket):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            # Optionally handle messages from client to server via WS (like interrupts)
            pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.remove(websocket)

async def start_ws_server():
    async with websockets.serve(ws_handler, "0.0.0.0", 8001):
        await asyncio.Future()  # run forever

async def main():
    logger.info("Starting browser MCP server and WebSocket streaming server...")
    await asyncio.gather(
        start_mcp_server(),
        start_ws_server()
    )

if __name__ == "__main__":
    asyncio.run(main())