#!/usr/bin/env python3
"""
MCP Server: Category-aware web search, website scraping, and date/time tools.
Supports stdio and streamable-http transports.

Protocol version: 2025-03-26
"""

import asyncio
import json
import logging
import os
import pathlib
import re
import sys
import time
import unicodedata
import contextlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, List
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, field_validator, model_validator
from cachetools import TTLCache
from zoneinfo import ZoneInfo
import filetype
import pymupdf
import pymupdf4llm
from dateutil import parser as date_parser
import trafilatura

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---
class MCPServerError(Exception):
    pass

class ConfigurationError(MCPServerError):
    pass

class SearXNGConnectionError(MCPServerError):
    pass

class WebScrapingError(MCPServerError):
    pass

class RateLimitExceededError(MCPServerError):
    pass

# --- Global Cache ---
website_cache: Optional[TTLCache] = None

# --- Rate Limiting ---
class RateLimiter:
    def __init__(self, requests_per_minute: int = 10, timeout_seconds: int = 60):
        self.requests_per_minute = requests_per_minute
        self.timeout_seconds = timeout_seconds
        self.domain_requests: Dict[str, List[float]] = {}

    def can_request(self, url: str) -> bool:
        domain = urlparse(url).netloc
        if not domain:
            return True
        current_time = time.time()
        if domain not in self.domain_requests:
            self.domain_requests[domain] = []
        self.domain_requests[domain] = [
            ts for ts in self.domain_requests[domain]
            if current_time - ts < self.timeout_seconds
        ]
        if len(self.domain_requests[domain]) >= self.requests_per_minute:
            return False
        self.domain_requests[domain].append(current_time)
        return True

    def get_remaining_time(self, url: str) -> float:
        domain = urlparse(url).netloc
        if not domain or domain not in self.domain_requests:
            return 0
        current_time = time.time()
        timestamps = [t for t in self.domain_requests[domain] if current_time - t < self.timeout_seconds]
        if len(timestamps) < self.requests_per_minute:
            return 0
        oldest = min(timestamps)
        return max(0, oldest + self.timeout_seconds - current_time)

# --- Cache Validation ---
class CacheValidator:
    @staticmethod
    def is_valid(cached_result: Dict[str, Any], max_age_minutes: int = 30) -> bool:
        if not cached_result:
            return False
        if "date_accessed" not in cached_result:
            return False
        try:
            date_accessed = date_parser.parse(cached_result["date_accessed"])
            now = datetime.now(timezone.utc)
            return (now - date_accessed).total_seconds() < (max_age_minutes * 60)
        except (ValueError, TypeError):
            return False

# --- Helpers ---
class Helpers:
    @staticmethod
    def get_base_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def generate_excerpt(content: str, max_length: int = 200) -> str:
        lines = content.splitlines()
        excerpt = ""
        for line in lines:
            if len(excerpt) + len(line) + 1 < max_length:
                excerpt += line + "\n"
            else:
                remaining = max_length - len(excerpt) - 4
                if remaining > 0:
                    excerpt += line[:remaining] + " ..."
                break
        return excerpt.strip() if excerpt else content[:max_length] + "..."

    @staticmethod
    def format_text_with_trafilatura(html_content: str, timeout: int) -> str:
        extracted = trafilatura.extract(
            html_content,
            favor_readability=True,
            include_comments=False,
            include_tables=True,
            timeout=timeout,
        )
        if not extracted:
            soup = BeautifulSoup(html_content, "html.parser")
            extracted = soup.get_text(separator="\n", strip=True)
            logger.warning("Trafilatura failed/timed out, falling back to basic text extraction.")
        lines = [unicodedata.normalize("NFKC", line).strip() for line in extracted.splitlines()]
        cleaned = [re.sub(r'\s{2,}', ' ', line) for line in lines if line]
        return Helpers.remove_emojis("\n".join(cleaned)).strip()

    @staticmethod
    def remove_emojis(text: str) -> str:
        return "".join(c for c in text if not unicodedata.category(c).startswith("So"))

    @staticmethod
    def truncate_to_n_words(text: str, word_limit: int) -> str:
        tokens = text.split()
        if len(tokens) <= word_limit:
            return text
        return " ".join(tokens[:word_limit]) + "..."

    @staticmethod
    def modify_reddit_url(url: str) -> str:
        match = re.match(r"^(https?://)(www\.)?(reddit\.com)(.*)$", url, re.IGNORECASE)
        if match:
            return f"{match.group(1)}old.reddit.com{match.group(4)}"
        return url

# --- Configuration ---
class ServerConfig(BaseModel):
    SEARXNG_ENGINE_API_BASE_URL: str = Field(default="http://host.docker.internal:8080/search")
    IGNORED_WEBSITES: str = Field(default="")
    RETURNED_SCRAPPED_PAGES_NO: int = Field(default=3, ge=1, le=20)
    SCRAPPED_PAGES_NO: int = Field(default=5, ge=1, le=30)
    PAGE_CONTENT_WORDS_LIMIT: int = Field(default=5000, ge=50, le=20000)
    CITATION_LINKS: bool = Field(default=True)
    desired_timezone: str = Field(default="America/New_York")
    TRAFILATURA_TIMEOUT: int = Field(default=15, ge=5, le=60)
    MAX_IMAGE_RESULTS: int = Field(default=10, ge=1, le=50)
    MAX_VIDEO_RESULTS: int = Field(default=10, ge=1, le=50)
    MAX_FILE_RESULTS: int = Field(default=5, ge=1, le=20)
    MAX_MAP_RESULTS: int = Field(default=5, ge=1, le=20)
    MAX_SOCIAL_RESULTS: int = Field(default=5, ge=1, le=20)
    SCRAPING_TIMEOUT: int = Field(default=20, ge=5, le=120)
    CACHE_MAXSIZE: int = Field(default=100, ge=10, le=1000)
    CACHE_TTL_MINUTES: int = Field(default=5, ge=1, le=1440)
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=10, ge=1, le=60)
    RATE_LIMIT_TIMEOUT_SECONDS: int = Field(default=60, ge=10, le=3600)
    CACHE_MAX_AGE_MINUTES: int = Field(default=30, ge=1, le=1440)
    MCP_TRANSPORT: str = Field(default="stdio")  # stdio | streamable-http | both
    MCP_HTTP_HOST: str = Field(default="0.0.0.0")
    MCP_HTTP_PORT: int = Field(default=8000, ge=1, le=65535)
    MCP_HTTP_PATH: str = Field(default="/mcp")

    @field_validator("SEARXNG_ENGINE_API_BASE_URL")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ConfigurationError(f"URL must start with http:// or https://, got {v}")
        return v

    @field_validator("desired_timezone")
    @classmethod
    def validate_tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
            return v
        except Exception as e:
            raise ConfigurationError(f"Invalid timezone: {v}. Error: {e}")

    @model_validator(mode="after")
    def check_limits(self):
        if self.SCRAPPED_PAGES_NO < self.RETURNED_SCRAPPED_PAGES_NO:
            raise ConfigurationError(
                f"SCRAPPED_PAGES_NO ({self.SCRAPPED_PAGES_NO}) must be >= RETURNED_SCRAPPED_PAGES_NO ({self.RETURNED_SCRAPPED_PAGES_NO})"
            )
        return self

    @classmethod
    def from_env(cls) -> "ServerConfig":
        """Load config from env vars with fallback to defaults."""
        defaults = cls().model_dump()
        env_config = {}
        for key in defaults:
            env_val = os.getenv(key)
            if env_val is not None:
                field_info = cls.model_fields[key]
                target_type = field_info.annotation
                try:
                    if target_type is bool:
                        env_config[key] = env_val.lower() == "true"
                    elif target_type is int:
                        env_config[key] = int(env_val)
                    elif target_type is str:
                        env_config[key] = env_val
                    else:
                        env_config[key] = env_val
                except Exception:
                    logger.warning(f"Invalid env var {key}={env_val}, using default")
        # Merge: defaults overridden by env
        merged = {**defaults, **env_config}
        return cls(**merged)


# --- Scraping Logic ---
async def process_search_result(
    result: Dict[str, Any], config: ServerConfig, client: httpx.AsyncClient
) -> Optional[Dict[str, Any]]:
    url = result.get("url")
    if not url:
        return None

    if config.IGNORED_WEBSITES:
        ignored = [s.strip() for s in config.IGNORED_WEBSITES.split(",")]
        if any(site in url for site in ignored):
            return {"url": url, "title": result.get("title", ""), "error": "Ignored website"}

    try:
        url_to_fetch = Helpers.modify_reddit_url(url)
        response = await client.get(url_to_fetch, timeout=config.SCRAPING_TIMEOUT)
        response.raise_for_status()
        html_content = response.text
        raw_content = response.content

        kind = filetype.guess(raw_content)
        if kind is not None and kind.mime == "application/pdf":
            doc = pymupdf.open(stream=raw_content, filetype="pdf")
            md_text = pymupdf4llm.to_markdown(doc)
            content = Helpers.truncate_to_n_words(md_text, config.PAGE_CONTENT_WORDS_LIMIT)
            excerpt = Helpers.generate_excerpt(md_text)
            return {
                "title": "A PDF document converted to Markdown",
                "url": url,
                "content": content,
                "excerpt": excerpt,
                "snippet": result.get("content", ""),
                "date_accessed": datetime.now(timezone.utc).isoformat(),
                "error": None,
            }
        else:
            soup = BeautifulSoup(html_content, "html.parser")
            title = result.get("title") or (soup.title.string if soup.title else "No title")
            title = Helpers.remove_emojis(unicodedata.normalize("NFKC", title.strip()))
            content = Helpers.format_text_with_trafilatura(html_content, config.TRAFILATURA_TIMEOUT)
            truncated = Helpers.truncate_to_n_words(content, config.PAGE_CONTENT_WORDS_LIMIT)
            excerpt = Helpers.generate_excerpt(content)
            return {
                "title": title,
                "url": url,
                "content": truncated,
                "excerpt": excerpt,
                "snippet": result.get("content", ""),
                "date_accessed": datetime.now(timezone.utc).isoformat(),
                "soup": soup,
                "error": None,
            }
    except httpx.HTTPStatusError as e:
        return {"url": url, "title": result.get("title", ""), "snippet": result.get("content", ""), "error": f"{e.response.status_code} {e.response.reason_phrase}"}
    except httpx.RequestError as e:
        return {"url": url, "title": result.get("title", ""), "snippet": result.get("content", ""), "error": f"Request failed: {e}"}
    except Exception as e:
        return {"url": url, "title": result.get("title", ""), "snippet": result.get("content", ""), "error": f"Unexpected error: {e}"}


async def fetch_website(url: str, config: ServerConfig, client: httpx.AsyncClient) -> Dict[str, Any]:
    url_to_fetch = Helpers.modify_reddit_url(url)
    response = await client.get(url_to_fetch, timeout=120)
    response.raise_for_status()
    html_content = response.text
    raw_content = response.content

    kind = filetype.guess(raw_content)
    if kind is not None and kind.mime == "application/pdf":
        doc = pymupdf.open(stream=raw_content, filetype="pdf")
        md_text = pymupdf4llm.to_markdown(doc)
        content = Helpers.truncate_to_n_words(md_text, config.PAGE_CONTENT_WORDS_LIMIT)
        excerpt = Helpers.generate_excerpt(md_text)
        return {
            "title": "A PDF document converted to Markdown",
            "url": url,
            "content": content,
            "excerpt": excerpt,
            "date_accessed": datetime.now(timezone.utc).isoformat(),
            "error": None,
            "soup": None,
        }
    else:
        soup = BeautifulSoup(html_content, "html.parser")
        page_title = soup.title.string if soup.title else "No title found"
        page_title = Helpers.remove_emojis(unicodedata.normalize("NFKC", page_title.strip()))
        content = Helpers.format_text_with_trafilatura(html_content, config.TRAFILATURA_TIMEOUT)
        truncated = Helpers.truncate_to_n_words(content, config.PAGE_CONTENT_WORDS_LIMIT)
        excerpt = Helpers.generate_excerpt(content)
        return {
            "title": page_title,
            "url": url,
            "content": truncated,
            "excerpt": excerpt,
            "date_accessed": datetime.now(timezone.utc).isoformat(),
            "error": None,
            "soup": soup,
        }


# --- FastMCP Server ---
mcp = FastMCP(
    "mcp-searxng-enhanced",
    instructions="Category-aware web search, website scraping, and date/time tools via SearXNG.",
    stateless_http=True,
    json_response=True,
)

# Global state
_config: Optional[ServerConfig] = None
_client: Optional[httpx.AsyncClient] = None

@mcp.tool()
async def search_web(
    query: str,
    engines: Optional[str] = None,
    category: Optional[str] = "general",
    safesearch: Optional[str] = None,
    time_range: Optional[str] = None,
) -> str:
    """
    Search the web via SearXNG.

    Args:
        query: The search query string.
        engines: Optional comma-separated SearXNG engines (e.g. "google,wikipedia").
        category: SearXNG category: general, images, videos, files, map, social media, news, it, science.
        safesearch: Safe search level: 0 (None), 1 (Moderate), 2 (Strict).
        time_range: Time filter: day, month, year.
    """
    global _config, _client
    if not _config or not _client:
        raise RuntimeError("Server not initialized")

    safe_category = (category or "general").lower().strip()
    params: Dict[str, Any] = {"q": query, "format": "json", "pageno": 1}
    if engines:
        params["engines"] = engines
    params["categories"] = safe_category
    if safesearch in ("0", "1", "2"):
        params["safesearch"] = safesearch
    if time_range in ("day", "month", "year"):
        params["time_range"] = time_range

    try:
        resp = await _client.get(_config.SEARXNG_ENGINE_API_BASE_URL, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        raise SearXNGConnectionError(f"SearXNG error: {e.response.status_code} {e.response.reason_phrase}") from e
    except httpx.RequestError as e:
        raise SearXNGConnectionError(f"SearXNG connection failed: {e}") from e
    except json.JSONDecodeError as e:
        raise SearXNGConnectionError(f"Invalid JSON from SearXNG: {e}") from e

    results = data.get("results", [])
    if not results:
        return "No results found."

    output_parts: List[str] = []
    category_limits = {
        "images": _config.MAX_IMAGE_RESULTS,
        "videos": _config.MAX_VIDEO_RESULTS,
        "files": _config.MAX_FILE_RESULTS,
        "map": _config.MAX_MAP_RESULTS,
        "social media": _config.MAX_SOCIAL_RESULTS,
    }
    limit = category_limits.get(safe_category, _config.RETURNED_SCRAPPED_PAGES_NO)

    if safe_category == "images":
        for i, r in enumerate(results[:limit]):
            if i > 0:
                output_parts.append("\n====================\n")
            output_parts.append(f"**Title:** {r.get('title', 'N/A')}")
            output_parts.append(f"**Image URL:** {r.get('img_src', 'N/A')}")
            output_parts.append(f"**Source Page:** {r.get('url', 'N/A')}")
            if r.get("img_src"):
                output_parts.append(f"\n![{r.get('title', 'Image')}]({r['img_src']})")
        return "\n".join(output_parts)

    elif safe_category == "videos":
        for i, r in enumerate(results[:limit]):
            if i > 0:
                output_parts.append("\n====================\n")
            output_parts.append(f"**Title:** {r.get('title', 'N/A')}")
            output_parts.append(f"**URL:** {r.get('url', 'N/A')}")
            if r.get("source"):
                output_parts.append(f"**Source:** {r['source']}")
            if r.get("iframe_src"):
                output_parts.append(f"**Embed URL:** {r['iframe_src']}")
            if r.get("content"):
                output_parts.append(f"\n**Description:**\n{r['content']}")
        return "\n".join(output_parts)

    elif safe_category == "files":
        for i, r in enumerate(results[:limit]):
            if i > 0:
                output_parts.append("\n====================\n")
            output_parts.append(f"**Title:** {r.get('title', 'N/A')}")
            output_parts.append(f"**URL:** {r.get('url', 'N/A')}")
            if r.get("format"):
                output_parts.append(f"**Format:** {r['format']}")
            if r.get("size"):
                output_parts.append(f"**Size:** {r['size']}")
            if r.get("content"):
                output_parts.append(f"\n**Snippet:**\n{r['content']}")
        return "\n".join(output_parts)

    elif safe_category == "map":
        for i, r in enumerate(results[:limit]):
            if i > 0:
                output_parts.append("\n====================\n")
            output_parts.append(f"**Title:** {r.get('title', 'N/A')}")
            output_parts.append(f"**Map URL:** {r.get('url', 'N/A')}")
            if r.get("address"):
                output_parts.append(f"**Address:** {r['address']}")
            if r.get("latitude") and r.get("longitude"):
                output_parts.append(f"**Coordinates:** {r['latitude']}, {r['longitude']}")
            if r.get("content"):
                output_parts.append(f"\n**Description:**\n{r['content']}")
        return "\n".join(output_parts)

    elif safe_category == "social media":
        for i, r in enumerate(results[:limit]):
            if i > 0:
                output_parts.append("\n====================\n")
            output_parts.append(f"**Title:** {r.get('title', 'N/A')}")
            output_parts.append(f"**URL:** {r.get('url', 'N/A')}")
            if r.get("content"):
                output_parts.append(f"\n**Content:**\n{r['content']}")
        return "\n".join(output_parts)

    else:
        # General web: scrape pages
        rate_limiter = RateLimiter(
            requests_per_minute=_config.RATE_LIMIT_REQUESTS_PER_MINUTE,
            timeout_seconds=_config.RATE_LIMIT_TIMEOUT_SECONDS,
        )
        tasks = []
        for r in results[:_config.SCRAPPED_PAGES_NO]:
            url = r.get("url", "")
            if url and not rate_limiter.can_request(url):
                domain = urlparse(url).netloc
                wait = rate_limiter.get_remaining_time(url)
                logger.warning(f"Rate limit for {domain}, skipping. Retry in {wait:.1f}s.")
                continue
            tasks.append(process_search_result(r, _config, _client))

        processed = await asyncio.gather(*tasks)
        valid = [p for p in processed if p and not p.get("error")]
        valid = valid[:_config.RETURNED_SCRAPPED_PAGES_NO]

        for i, res in enumerate(valid):
            if i > 0:
                output_parts.append("\n====================\n")
            output_parts.append(f"**Title:** {res.get('title', 'N/A')}")
            output_parts.append(f"**URL:** {res.get('url', 'N/A')}")
            if res.get("snippet"):
                output_parts.append(f"\n**Snippet:**\n{res['snippet']}")
            output_parts.append("\n\n**Content:**")
            output_parts.append(res.get("content", ""))
        return "\n".join(output_parts)


@mcp.tool()
async def get_website(url: str) -> str:
    """
    Scrape content from a web page or PDF.
    Automatically converts Reddit URLs to old.reddit.com.
    Results are cached.

    Args:
        url: The URL to scrape.
    """
    global _config, _client, website_cache
    if not _config or not _client:
        raise RuntimeError("Server not initialized")

    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url

    rate_limiter = RateLimiter(
        requests_per_minute=_config.RATE_LIMIT_REQUESTS_PER_MINUTE,
        timeout_seconds=_config.RATE_LIMIT_TIMEOUT_SECONDS,
    )
    if not rate_limiter.can_request(url):
        wait = rate_limiter.get_remaining_time(url)
        raise RateLimitExceededError(
            f"Rate limit exceeded for {parsed.netloc}. Retry in {wait:.1f}s."
        )

    cached = website_cache.get(url) if website_cache else None
    if cached and CacheValidator.is_valid(cached, _config.CACHE_MAX_AGE_MINUTES):
        result = cached
    else:
        result = await fetch_website(url, _config, _client)
        if not result.get("error") and website_cache is not None:
            cache_copy = result.copy()
            cache_copy.pop("soup", None)
            website_cache[url] = cache_copy

    if result.get("error"):
        return f"Error accessing {result.get('url', url)}: {result['error']}"

    lines = [
        f"**Title:** {result.get('title', 'N/A')}",
        f"**URL:** {result.get('url', 'N/A')}",
        f"**Date Accessed:** {result.get('date_accessed', 'N/A')}",
        "\n**Excerpt:**",
        result.get("excerpt", ""),
        "\n\n**Content:**",
        result.get("content", ""),
    ]
    return "\n".join(lines)


@mcp.tool()
async def get_current_datetime() -> str:
    """Get the current date and time in the configured timezone."""
    global _config
    if not _config:
        raise RuntimeError("Server not initialized")
    now_utc = datetime.now(timezone.utc)
    try:
        tz = ZoneInfo(_config.desired_timezone)
    except Exception:
        tz = timezone.utc
    now_local = now_utc.astimezone(tz)
    formatted = now_local.strftime("%A, %B %d, %Y at %I:%M %p (%Z)")
    return f"The current date and time is {formatted}"


async def init_server():
    global _config, _client, website_cache
    _config = ServerConfig.from_env()
    logger.info(f"Initialized with timezone: {_config.desired_timezone}")
    logger.info(f"SearXNG endpoint: {_config.SEARXNG_ENGINE_API_BASE_URL}")
    logger.info(f"Transport mode: {_config.MCP_TRANSPORT}")
    website_cache = TTLCache(
        maxsize=_config.CACHE_MAXSIZE,
        ttl=timedelta(minutes=_config.CACHE_TTL_MINUTES).total_seconds(),
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    _client = httpx.AsyncClient(headers=headers, follow_redirects=True)
    logger.info("HTTP client ready")


async def shutdown_server():
    global _client
    if _client:
        await _client.aclose()
    logger.info("Shutdown complete")


# --- Entrypoint ---
async def _run_stdio_async():
    await init_server()
    try:
        logger.info("Starting MCP server with stdio transport")
        mcp.run(transport="stdio")
    finally:
        await shutdown_server()


def run_stdio():
    asyncio.run(_run_stdio_async())


def run_http():
    """Run with streamable-http transport via uvicorn."""
    asyncio.run(init_server())
    config = ServerConfig.from_env()
    host = config.MCP_HTTP_HOST
    port = config.MCP_HTTP_PORT
    path = config.MCP_HTTP_PATH
    logger.info(f"Starting MCP server with streamable-http on http://{host}:{port}{path}")
    mcp.settings.streamable_http_path = path
    app = mcp.streamable_http_app()
    uvicorn.run(app, host=host, port=port, log_level="info", proxy_headers=True, forwarded_allow_ips="*")


def run_both():
    """Run stdio in background and HTTP in foreground."""
    import threading
    logger.info("Starting MCP server with BOTH transports")
    stdio_thread = threading.Thread(target=run_stdio, daemon=True)
    stdio_thread.start()
    run_http()


if __name__ == "__main__":
    config = ServerConfig.from_env()
    transport = config.MCP_TRANSPORT.lower().strip()

    if transport == "stdio":
        run_stdio()
    elif transport == "streamable-http":
        run_http()
    elif transport == "both":
        run_both()
    else:
        logger.error(f"Unknown MCP_TRANSPORT: {transport}. Use 'stdio', 'streamable-http', or 'both'.")
        sys.exit(1)
