# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..."
    . .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "No .venv directory found. Please ensure Python dependencies are installed."
    Write-Host "You can create a virtual environment and install dependencies by running:"
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\Activate.ps1"
    Write-Host "  pip install -r requirements.txt"
}

# Check for SEARXNG_ENGINE_API_BASE_URL
if (-not $env:SEARXNG_ENGINE_API_BASE_URL) {
    $searxng_url = Read-Host "Enter your SearXNG Engine API Base URL (e.g., http://127.0.0.1:8080/search)"
    if ([string]::IsNullOrWhiteSpace($searxng_url)) {
        Write-Error "SearXNG URL is required. Exiting."
        exit 1
    }
    $env:SEARXNG_ENGINE_API_BASE_URL = $searxng_url
}

# Check for DESIRED_TIMEZONE (optional, provide default if not set)
if (-not $env:DESIRED_TIMEZONE) {
    $timezone_input = Read-Host "Enter your desired timezone (e.g., America/New_York, default: America/New_York)"
    if (-not [string]::IsNullOrWhiteSpace($timezone_input)) {
        $env:DESIRED_TIMEZONE = $timezone_input
    } else {
        $env:DESIRED_TIMEZONE = "America/New_York" # Default if user provides no input
    }
}

Write-Host "Starting MCP SearXNG Enhanced Server..."
Write-Host "Using SEARXNG_ENGINE_API_BASE_URL: $env:SEARXNG_ENGINE_API_BASE_URL"
Write-Host "Using DESIRED_TIMEZONE: $env:DESIRED_TIMEZONE"
# Add other environment variables here if needed, following the same pattern

python mcp_server.py
