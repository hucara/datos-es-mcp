import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import Awaitable, Callable

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from helpers.logging import MAIN_LOGGER_NAME, UVICORN_LOGGING_CONFIG
from helpers.matomo import track_matomo
from helpers.sentry import init_sentry
from tools import register_tools

init_sentry()

SERVER_START_TIME = datetime.now(timezone.utc)

logger = logging.getLogger(MAIN_LOGGER_NAME)

transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "localhost:*",
        "127.0.0.1:*",
    ],
    allowed_origins=[
        "http://localhost:*",
        "http://127.0.0.1:*",
    ],
)

mcp = FastMCP(
    "datos-es MCP server",
    transport_security=transport_security,
    stateless_http=True,
)
register_tools(mcp)


def with_monitoring(
    inner_app: Callable[[dict, Callable, Callable], Awaitable[None]],
):
    async def app(scope, receive, send):
        if scope["type"] == "http":
            path: str = scope.get("path", "")

            if path == "/health":
                try:
                    app_version = version("datos-es-mcp")
                except PackageNotFoundError:
                    app_version = "unknown"

                body = json.dumps(
                    {
                        "status": "ok",
                        "uptime_since": SERVER_START_TIME.isoformat(),
                        "version": app_version,
                        "env": os.getenv("MCP_ENV", "unknown"),
                    }
                ).encode("utf-8")
                headers = [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("utf-8")),
                ]
                await send(
                    {"type": "http.response.start", "status": 200, "headers": headers}
                )
                await send({"type": "http.response.body", "body": body})
                return

            headers_dict: dict[str, str] = {
                k.decode("utf-8"): v.decode("utf-8")
                for k, v in scope.get("headers", [])
            }
            host: str = headers_dict.get("host", "localhost")
            full_url: str = f"https://{host}{path}"

            asyncio.create_task(
                track_matomo(url=full_url, path=path, headers=headers_dict)
            )

        await inner_app(scope, receive, send)

    return app


asgi_app = with_monitoring(mcp.streamable_http_app())

if __name__ == "__main__":
    port_str = os.getenv("MCP_PORT", "8000")
    try:
        port = int(port_str)
    except ValueError:
        print(
            f"Error: Invalid MCP_PORT environment variable: {port_str}",
            file=sys.stderr,
        )
        sys.exit(1)

    host = os.getenv("MCP_HOST", "0.0.0.0")
    uvicorn.run(
        asgi_app,
        host=host,
        port=port,
        log_level="info",
        log_config=UVICORN_LOGGING_CONFIG,
    )
