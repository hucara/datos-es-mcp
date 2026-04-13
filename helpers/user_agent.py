"""User-Agent sent to Spanish open data services for identification."""

try:
    from importlib.metadata import version

    USER_AGENT = f"datos-es-mcp/{version('datos-es-mcp')}"
except Exception:
    USER_AGENT = "datos-es-mcp/dev"
