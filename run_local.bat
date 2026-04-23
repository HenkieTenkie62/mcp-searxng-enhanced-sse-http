@echo off
REM Run MCP SearXNG Enhanced Server locally (Windows CMD)

REM Load .env if it exists
if exist .env (
    for /f "usebackq tokens=1,* delims=" %%a in (".env") do (
        echo %%a | findstr /b "#" >nul || set "%%a"
    )
)

REM Defaults
if "%MCP_TRANSPORT%"=="" set MCP_TRANSPORT=stdio
if "%MCP_HTTP_HOST%"=="" set MCP_HTTP_HOST=0.0.0.0
if "%MCP_HTTP_PORT%"=="" set MCP_HTTP_PORT=8000
if "%MCP_HTTP_PATH%"=="" set MCP_HTTP_PATH=/mcp

echo Starting MCP SearXNG Enhanced Server...
echo Transport: %MCP_TRANSPORT%

python mcp_server.py
