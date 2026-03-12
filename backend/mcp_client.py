import asyncio
import logging
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)

class MCPClient:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session = None
        self.exit_stack = AsyncExitStack()

    async def connect(self):
        """Connect to the MCP server via SSE."""
        if self.session:
            return

        try:
            sse_transport = await self.exit_stack.enter_async_context(sse_client(self.server_url))
            self.read_stream, self.write_stream = sse_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.read_stream, self.write_stream))

            await self.session.initialize()
            logger.info("Connected to MCP server")
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            raise

    async def get_available_tools(self):
        """List available tools from the MCP server."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        response = await self.session.list_tools()
        return response.tools

    async def execute_tool(self, tool_name: str, arguments: dict):
        """Execute a tool via the MCP server."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server")

        logger.info(f"Executing MCP Tool: {tool_name}")
        result = await self.session.call_tool(tool_name, arguments)
        return result

    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.exit_stack:
            await self.exit_stack.aclose()
            self.session = None

# Global instance for the app
import os
server_url = os.environ.get("MCP_SERVER_URL", "http://research_mcp:8000/sse")
mcp_client = MCPClient(server_url=server_url)
