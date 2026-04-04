import asyncio
import logging
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.sse import sse_client
from backend.config import get_secret, CIRCUIT_FAILURE_THRESHOLD, CIRCUIT_RECOVERY_TIMEOUT, CACHE_RETRY_COUNT
from backend.error_handling import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)

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

    async def connect(self):
        """Connect to the MCP server via SSE with retries."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        if self.session and self._loop == current_loop:
            return

        # If session exists but loop changed, reset the stack for the new loop context
        if self.session:
            logger.info(f"New event loop detected, resetting MCP session stack for {self.server_url}")
            self.session = None
            self.exit_stack = AsyncExitStack()

        self._loop = current_loop

        max_retries = CACHE_RETRY_COUNT
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                headers = {"X-MCP-API-KEY": get_secret(self.api_key_secret_name, "")}
                sse_transport = await self.exit_stack.enter_async_context(sse_client(self.server_url, headers=headers))
                self.read_stream, self.write_stream = sse_transport
                self.session = await self.exit_stack.enter_async_context(ClientSession(self.read_stream, self.write_stream))

                await self.session.initialize()
                logger.info(f"Connected to MCP server at {self.server_url}")
                return
            except Exception as e:
                logger.warning(f"Failed to connect to MCP server {self.server_url} (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5
                else:
                    logger.error(f"Max retries reached. Failed to connect to MCP server {self.server_url}: {e}")
                    raise

    async def get_available_tools(self):
        """List available tools from the MCP server."""
        if not self.session:
            raise RuntimeError(f"Not connected to MCP server {self.server_url}")
        response = await self.session.list_tools()
        return response.tools

    async def execute_tool(self, tool_name: str, arguments: dict):
        """Execute a tool via the MCP server with circuit breaker protection."""
        if not self.session:
            raise RuntimeError(f"Not connected to MCP server {self.server_url}")

        async def _execute():
            logger.info(f"Executing MCP Tool '{tool_name}' on {self.server_url}")
            return await self.session.call_tool(tool_name, arguments)

        try:
            result = await self.circuit_breaker.call_async(_execute)
            return result
        except CircuitOpenError:
            logger.warning(f"Circuit open for MCP server {self.server_url}, rejecting tool '{tool_name}'")
            raise

    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.exit_stack:
            await self.exit_stack.aclose()
            self.session = None

# Global instances for the app
import os
tavily_server_url = os.environ.get("TAVILY_MCP_SERVER_URL", "http://tavily_mcp:8000/sse")
playwright_server_url = os.environ.get("PLAYWRIGHT_MCP_SERVER_URL", "http://playwright_mcp:8001/sse")

tavily_client = MCPClient(server_url=tavily_server_url, api_key_secret_name="MCP_API_KEY")
playwright_client = MCPClient(server_url=playwright_server_url, api_key_secret_name="PLAYWRIGHT_MCP_API_KEY")
