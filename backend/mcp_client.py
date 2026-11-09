import asyncio
import base64
import logging
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.sse import sse_client
from backend.config import get_secret, CIRCUIT_FAILURE_THRESHOLD, CIRCUIT_RECOVERY_TIMEOUT, CACHE_RETRY_COUNT, TIMEOUT_MCP_TOOL_CALL
from backend.error_handling import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)

# Timeout for establishing the SSE connection + session initialization
_CONNECT_TIMEOUT = 30


class MCPClient:
    def __init__(self, server_url: str, api_key_secret_name: str = "MCP_API_KEY"):
        self.server_url = server_url
        self.api_key_secret_name = api_key_secret_name
        self.session = None
        self.exit_stack = AsyncExitStack()
        self._loop = None
        self.read_stream = None
        self.write_stream = None

        # Circuit breaker for this MCP client
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=CIRCUIT_FAILURE_THRESHOLD,
            recovery_timeout=CIRCUIT_RECOVERY_TIMEOUT
        )

    def _reset_state(self):
        """Abandon current session state without awaiting cleanup.

        The old exit_stack is intentionally NOT closed here because it was
        created on a now-dead event loop.  Awaiting aclose() on resources
        bound to a closed loop can hang indefinitely.  The underlying TCP
        connections will be reclaimed by the OS via keepalive/timeout.
        """
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.read_stream = None
        self.write_stream = None

    async def _close_and_reset_state(self):
        """Attempts to close the current exit stack before resetting state,
        protecting against hanging if the event loop is closed.
        """
        if self.exit_stack:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    await asyncio.wait_for(self.exit_stack.aclose(), timeout=5.0)
            except Exception:
                pass
        self._reset_state()

    async def connect(self):
        """Connect to the MCP server via SSE with retries."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        if self.session and self._loop == current_loop:
            return

        # If session exists but loop changed, abandon old state (see _reset_state docstring)
        if self.session:
            logger.info(f"Event loop changed, abandoning stale MCP session for {self.server_url}")
            self._reset_state()

        self._loop = current_loop

        max_retries = CACHE_RETRY_COUNT
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                await asyncio.wait_for(
                    self._establish_session(),
                    timeout=_CONNECT_TIMEOUT
                )
                logger.info(f"Connected to MCP server at {self.server_url}")
                return
            except asyncio.TimeoutError:
                logger.warning(f"MCP connect timed out after {_CONNECT_TIMEOUT}s for {self.server_url} (attempt {attempt+1}/{max_retries})")
                await self._close_and_reset_state()
                if attempt >= max_retries - 1:
                    raise ConnectionError(f"Failed to connect to MCP server {self.server_url}: connection timed out")
            except Exception as e:
                logger.warning(f"Failed to connect to MCP server {self.server_url} (attempt {attempt+1}/{max_retries}): {e}")
                await self._close_and_reset_state()
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5
                else:
                    logger.error(f"Max retries reached. Failed to connect to MCP server {self.server_url}: {e}")
                    raise

    async def _establish_session(self):
        """Create a fresh SSE transport and MCP session."""
        headers = {"X-MCP-API-KEY": get_secret(self.api_key_secret_name, "")}
        sse_transport = await self.exit_stack.enter_async_context(sse_client(self.server_url, headers=headers))
        self.read_stream, self.write_stream = sse_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.read_stream, self.write_stream))
        await self.session.initialize()

    async def get_available_tools(self):
        """List available tools from the MCP server."""
        if not self.session:
            raise RuntimeError(f"Not connected to MCP server {self.server_url}")
        response = await self.session.list_tools()
        return response.tools

    async def execute_tool(self, tool_name: str, arguments: dict):
        """Execute a tool via MCP with 1 internal retry before counting against circuit breaker."""
        # Always ensure a fresh connection — the singleton client is shared
        # across TaskWorker threads that each have their own event loop.
        await self.connect()

        if not self.session:
            raise RuntimeError(f"Not connected to MCP server {self.server_url}")

        async def _execute_with_retry():
            last_err = None
            for attempt in range(2):  # 1 retry = 2 total attempts
                try:
                    logger.info(f"Executing MCP Tool '{tool_name}' on {self.server_url}")
                    return await asyncio.wait_for(
                        self.session.call_tool(tool_name, arguments),
                        timeout=TIMEOUT_MCP_TOOL_CALL
                    )
                except asyncio.TimeoutError:
                    last_err = TimeoutError(
                        f"MCP tool '{tool_name}' timed out after {TIMEOUT_MCP_TOOL_CALL}s"
                    )
                    logger.warning(f"MCP tool '{tool_name}' timed out on {self.server_url} (attempt {attempt+1})")
                    if attempt == 0:
                        # Force fresh connection before retry
                        await self._close_and_reset_state()
                        await self.connect()
                except Exception as e:
                    last_err = e
                    if attempt == 0:
                        logger.warning(f"MCP tool '{tool_name}' failed, retrying with fresh connection: {e}")
                        await self._close_and_reset_state()
                        await self.connect()
                        if not self.session:
                            raise
            raise last_err

        try:
            result = await self.circuit_breaker.call_async(_execute_with_retry)
            return result
        except CircuitOpenError:
            logger.warning(f"Circuit open for MCP server {self.server_url}, rejecting tool '{tool_name}'")
            raise

    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.exit_stack:
            try:
                await asyncio.wait_for(self.exit_stack.aclose(), timeout=5)
            except (asyncio.TimeoutError, Exception):
                pass
            self._reset_state()

# Global instances for the app
import os
tavily_server_url = os.environ.get("TAVILY_MCP_SERVER_URL", "http://tavily_mcp:8000/sse")
playwright_server_url = os.environ.get("PLAYWRIGHT_MCP_SERVER_URL", "http://playwright_mcp:8001/sse")

tavily_client = MCPClient(server_url=tavily_server_url, api_key_secret_name="MCP_API_KEY")
playwright_client = MCPClient(server_url=playwright_server_url, api_key_secret_name="PLAYWRIGHT_MCP_API_KEY")


def portal_vnc_auth_header() -> dict:
    """
    HTTP Basic credential for the portal VNC (websockify in the playwright_mcp container).

    The password is the playwright_mcp API key; the app's proxies add this header server-side so the key
    never reaches the browser.

    Returns:
        `{"Authorization": "Basic ..."}`, or `{}` when the key is not configured.
    """
    key = get_secret("PLAYWRIGHT_MCP_API_KEY", "")
    if not key:
        return {}
    return {"Authorization": "Basic " + base64.b64encode(f"portal:{key}".encode("utf-8")).decode("ascii")}
