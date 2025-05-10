#!/bin/bash

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
  echo "Activating virtual environment..."
  source .venv/bin/activate
else
  echo "No .venv directory found. Please ensure Python dependencies are installed."
  echo "You can create a virtual environment and install dependencies by running:"
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
fi

# Check for SEARXNG_ENGINE_API_BASE_URL
if [ -z "$SEARXNG_ENGINE_API_BASE_URL" ]; then
  read -p "Enter your SearXNG Engine API Base URL (e.g., http://127.0.0.1:8080/search): " searxng_url
  if [ -z "$searxng_url" ]; then
    echo "SearXNG URL is required. Exiting."
    exit 1
  fi
  export SEARXNG_ENGINE_API_BASE_URL="$searxng_url"
fi

# Check for DESIRED_TIMEZONE (optional, provide default if not set)
if [ -z "$DESIRED_TIMEZONE" ]; then
  read -p "Enter your desired timezone (e.g., America/New_York, default: America/New_York): " timezone_input
  if [ -n "$timezone_input" ]; then
    export DESIRED_TIMEZONE="$timezone_input"
  else
    export DESIRED_TIMEZONE="America/New_York" # Default if user provides no input
  fi
fi

echo "Starting MCP SearXNG Enhanced Server..."
echo "Using SEARXNG_ENGINE_API_BASE_URL: $SEARXNG_ENGINE_API_BASE_URL"
echo "Using DESIRED_TIMEZONE: $DESIRED_TIMEZONE"
# Add other environment variables here if needed, following the same pattern

python mcp_server.py
