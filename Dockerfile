# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the local code to the container
COPY mcp_server.py .

# Define environment variables with default values
# Core configuration
ENV SEARXNG_ENGINE_API_BASE_URL="http://host.docker.internal:8080/search"
ENV DESIRED_TIMEZONE="America/New_York"
ENV ODS_CONFIG_PATH="/config/ods_config.json"

# Search results configuration
ENV IGNORED_WEBSITES=""
ENV RETURNED_SCRAPPED_PAGES_NO="3"
ENV SCRAPPED_PAGES_NO="5"
ENV PAGE_CONTENT_WORDS_LIMIT="5000"
ENV CITATION_LINKS="True"

# Category-specific result limits
ENV MAX_IMAGE_RESULTS="10"
ENV MAX_VIDEO_RESULTS="10"
ENV MAX_FILE_RESULTS="5"
ENV MAX_MAP_RESULTS="5"
ENV MAX_SOCIAL_RESULTS="5"

# Performance and limits
ENV TRAFILATURA_TIMEOUT="15"
ENV SCRAPING_TIMEOUT="20"
ENV CACHE_MAXSIZE="100"
ENV CACHE_TTL_MINUTES="5"
ENV CACHE_MAX_AGE_MINUTES="30"
ENV RATE_LIMIT_REQUESTS_PER_MINUTE="10"
ENV RATE_LIMIT_TIMEOUT_SECONDS="60"

# Run mcp_server.py when the container launches
CMD ["python", "mcp_server.py"]
