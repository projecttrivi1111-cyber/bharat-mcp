"""
Bharat MCP — SSE Transport Server
Compatible with MCPize discovery process.
"""
import asyncio
import json
import os
import sys
import importlib.util

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.requests import Request

from mcp.server import Server, InitializationOptions, NotificationOptions
from mcp.server.sse import SseServerTransport
from mcp import types

# ── Import existing tools ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

spec = importlib.util.spec_from_file_location(
    "bharath_mcp",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "bharath_mcp.py")
)
bharath_mcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bharath_mcp)

TOOLS = bharath_mcp.TOOLS

# ── Create MCP Server ────────────────────────────────────────────────
mcp_server = Server("bharath-mcp")

@mcp_server.list_tools()
async def list_tools():
    tools = []
    for name, tool in TOOLS.items():
        tools.append(
            types.Tool(
                name=name,
                description=tool["description"],
                inputSchema=tool["parameters"],
            )
        )
    return tools

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name not in TOOLS:
        raise ValueError(f"Unknown tool: {name}")
    func = TOOLS[name]["function"]
    result = func(**arguments)
    return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

# ── SSE Transport ───────────────────────────────────────────────────
sse = SseServerTransport("/messages")

async def handle_sse(request: Request):
    """GET /sse — SSE stream endpoint."""
    async with sse.connect_sse(request.scope, request.receive, request._send) as (
        read_stream,
        write_stream,
    ):
        await mcp_server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="bharath-mcp",
                server_version="1.0.0",
                capabilities=mcp_server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                ),
            ),
        )

async def handle_messages(request: Request):
    """POST /messages — Client message endpoint."""
    await sse.handle_post_message(request.scope, request.receive, request._send)

async def health(request):
    return JSONResponse({"status": "ok", "server": "bharath-mcp", "tools": len(TOOLS)})

async def tools_list(request):
    tools = []
    for name, tool in TOOLS.items():
        tools.append({"name": name, "description": tool["description"]})
    return JSONResponse({"tools": tools, "count": len(tools)})

# ── App ─────────────────────────────────────────────────────────────
app = Starlette(
    routes=[
        Route("/health", health),
        Route("/tools", tools_list),
        Route("/sse", handle_sse, methods=["GET"]),
        Route("/messages", handle_messages, methods=["POST"]),
    ],
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Bharat MCP SSE server on {host}:{port}", file=sys.stderr)
    uvicorn.run(app, host=host, port=port)
