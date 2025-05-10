@echo off

REM Activate virtual environment if it exists
IF EXIST .venv\Scripts\activate.bat (
    echo Activating virtual environment...
    CALL .venv\Scripts\activate.bat
) ELSE (
    echo No .venv directory found. Please ensure Python dependencies are installed.
    echo You can create a virtual environment and install dependencies by running:
    echo   python -m venv .venv
    echo   .\.venv\Scripts\activate.bat
    echo   pip install -r requirements.txt
)

REM Check for SEARXNG_ENGINE_API_BASE_URL
IF "%SEARXNG_ENGINE_API_BASE_URL%"=="" (
    set /p searxng_url="Enter your SearXNG Engine API Base URL (e.g., http://127.0.0.1:8080/search): "
    IF "%searxng_url%"=="" (
        echo SearXNG URL is required. Exiting.
        exit /b 1
    )
    set SEARXNG_ENGINE_API_BASE_URL=%searxng_url%
)

REM Check for DESIRED_TIMEZONE (optional, provide default if not set)
IF "%DESIRED_TIMEZONE%"=="" (
    set /p timezone_input="Enter your desired timezone (e.g., America/New_York, default: America/New_York): "
    IF NOT "%timezone_input%"=="" (
        set DESIRED_TIMEZONE=%timezone_input%
    ) ELSE (
        set DESIRED_TIMEZONE=America/New_York
    )
)

echo Starting MCP SearXNG Enhanced Server...
echo Using SEARXNG_ENGINE_API_BASE_URL: %SEARXNG_ENGINE_API_BASE_URL%
echo Using DESIRED_TIMEZONE: %DESIRED_TIMEZONE%
REM Add other environment variables here if needed, following the same pattern

python mcp_server.py
