"""
Bharat MCP — Dual Transport Server (SSE + Streamable HTTP)
Compatible with MCPize discovery process.

Endpoints:
- GET  /sse       — SSE transport (for SSE clients)
- POST /messages  — SSE message endpoint
- ALL  /mcp       — Streamable HTTP transport (for MCPize discovery)
- GET  /health    — Health check
- GET  /tools     — List available tools
"""
import json
import os
import sys
import importlib.util
from contextlib import asynccontextmanager

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
    """GET /sse — SSE stream endpoint. Returns ASGI callable for Starlette compat."""
    async def asgi_app(scope, receive, send):
        async with sse.connect_sse(scope, receive, send) as (
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

    return asgi_app


async def handle_messages(request: Request):
    """POST /messages — SSE client message endpoint."""
    await sse.handle_post_message(request.scope, request.receive, request._send)


# ── Streamable HTTP Transport ───────────────────────────────────────
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

session_manager = StreamableHTTPSessionManager(
    app=mcp_server,
    event_store=None,
    json_response=True,
    stateless=True,
)


@asynccontextmanager
async def lifespan(app):
    """Manage the session manager lifecycle."""
    async with session_manager.run():
        yield


class MCPApp:
    """ASGI app that delegates to the Streamable HTTP session manager.
    
    This is a class-based endpoint (not a function), so Starlette's Route
    treats it as a raw ASGI app and calls it directly with (scope, receive, send)
    without wrapping it in request_response().
    """
    async def __call__(self, scope, receive, send):
        await session_manager.handle_request(scope, receive, send)


mcp_app = MCPApp()


async def health(request):
    return JSONResponse({"status": "ok", "server": "bharath-mcp", "tools": len(TOOLS)})


async def tools_list(request):
    tools = []
    for name, tool in TOOLS.items():
        tools.append({"name": name, "description": tool["description"]})
    return JSONResponse({"tools": tools, "count": len(TOOLS)})


# ── App ─────────────────────────────────────────────────────────────
# redirect_slashes=False prevents 307 redirects on /mcp → /mcp/
app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/health", health),
        Route("/tools", tools_list),
        Route("/sse", handle_sse, methods=["GET"]),
        Route("/messages", handle_messages, methods=["POST"]),
        Route("/mcp", mcp_app, methods=["GET", "POST", "DELETE"]),
    ],
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Bharat MCP server on {host}:{port}", file=sys.stderr)
    uvicorn.run(app, host=host, port=port)
