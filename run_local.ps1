# Run MCP SearXNG Enhanced Server locally (PowerShell)

# Load .env if it exists
if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match "^([^#][^=]*)=(.*)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
}

# Defaults
$env:MCP_TRANSPORT = if ($env:MCP_TRANSPORT) { $env:MCP_TRANSPORT } else { "stdio" }
$env:MCP_HTTP_HOST = if ($env:MCP_HTTP_HOST) { $env:MCP_HTTP_HOST } else { "0.0.0.0" }
$env:MCP_HTTP_PORT = if ($env:MCP_HTTP_PORT) { $env:MCP_HTTP_PORT } else { "8000" }
$env:MCP_HTTP_PATH = if ($env:MCP_HTTP_PATH) { $env:MCP_HTTP_PATH } else { "/mcp" }

Write-Host "Starting MCP SearXNG Enhanced Server..."
Write-Host "Transport: $($env:MCP_TRANSPORT)"

python mcp_server.py
