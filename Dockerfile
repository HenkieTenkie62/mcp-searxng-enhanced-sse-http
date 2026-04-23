# Multi-stage build for smaller image
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY mcp_server.py .

# Expose HTTP port for streamable-http transport
EXPOSE 8000

# Health check for HTTP mode (ignored in stdio mode, but useful for orchestrators)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/mcp')" || exit 1

# Default environment variables
ENV SEARXNG_ENGINE_API_BASE_URL="http://host.docker.internal:8080/search"
ENV DESIRED_TIMEZONE="Europe/Amsterdam"
ENV MCP_TRANSPORT="stdio"
ENV MCP_HTTP_HOST="0.0.0.0"
ENV MCP_HTTP_PORT="8000"
ENV MCP_HTTP_PATH="/mcp"

ENV PYTHONUNBUFFERED=1

CMD ["python", "mcp_server.py"]
