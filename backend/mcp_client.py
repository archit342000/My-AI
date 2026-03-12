import asyncio
import logging
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

class MCPClient:
    def __init__(self, server_script_path: str):
        self.server_script_path = server_script_path
        self.session = None
        self.exit_stack = AsyncExitStack()

    async def connect(self):
        """Connect to the MCP server via stdio."""
        if self.session:
            return

        server_params = StdioServerParameters(
            command="python3",
            args=[self.server_script_path],
            env=None  # Inherit env so it gets TAVILY_API_KEY
        )

        try:
            stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

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
server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mcp_server", "server.py"))
mcp_client = MCPClient(server_script_path=server_path)
