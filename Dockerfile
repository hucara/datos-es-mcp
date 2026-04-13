FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files first for layer caching
COPY pyproject.toml .
COPY README.md .

# Install dependencies
RUN uv sync --no-dev --no-editable

# Copy source code
COPY main.py .
COPY helpers/ helpers/
COPY tools/ tools/

# Expose the MCP server port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uv", "run", "main.py"]
