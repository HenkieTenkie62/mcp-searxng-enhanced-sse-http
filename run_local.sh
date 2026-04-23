#!/usr/bin/env bash
set -e

# Load .env if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Default to stdio if not set
export MCP_TRANSPORT="${MCP_TRANSPORT:-stdio}"
export MCP_HTTP_HOST="${MCP_HTTP_HOST:-0.0.0.0}"
export MCP_HTTP_PORT="${MCP_HTTP_PORT:-8000}"
export MCP_HTTP_PATH="${MCP_HTTP_PATH:-/mcp}"

echo "Starting MCP SearXNG Enhanced Server..."
echo "Transport: $MCP_TRANSPORT"

python mcp_server.py
