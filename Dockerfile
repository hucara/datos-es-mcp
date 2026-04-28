FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy source code
COPY pyproject.toml .
COPY README.md .
COPY main.py .
COPY helpers/ helpers/
COPY tools/ tools/

# Install dependencies
RUN uv sync --no-dev --no-editable

# Expose the MCP server port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uv", "run", "main.py"]
