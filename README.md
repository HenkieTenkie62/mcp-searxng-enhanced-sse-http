# MCP SearXNG Enhanced Server (HTTP Edition)

> **Fork van [OvertliDS/mcp-searxng-enhanced](https://github.com/OvertliDS/mcp-searxng-enhanced)** — nu met **officiële MCP Python SDK**, **Streamable HTTP transport**, en **protocol 2025-03-26**.

Een [Model Context Protocol](https://modelcontextprotocol.io) server voor categorie-bewust webzoeken, website scraping, en datum/tijd tools. Geïntegreerd met [SearXNG](https://github.com/searxng/searxng) en compatibel met moderne MCP clients zoals Claude Desktop, Cline, Continue, en Cursor.

## Belangrijkste wijzigingen ten opzichte van upstream

- **Officiële MCP Python SDK** (`FastMCP`) — geen handmatige JSON-RPC/stdio spaghetti meer
- **Drie transport modes**: `stdio` (backward compatible), `streamable-http`, of `both`
- **Protocol 2025-03-26** — de huidige MCP standaard
- **Multi-stage Docker build** — kleinere image (~60% reductie)
- **Docker Compose** — one-command deployment
- **Pydantic v2** — modernere configuratie validatie
- **Uvicorn** — productie-klare ASGI server voor HTTP mode

> **Nota bene:** Het oude **SSE (Server-Sent Events) transport** uit MCP protocol 2024-11-05 is **deprecated**. De nieuwe standaard is **Streamable HTTP** (Maart 2025). Deze fork implementeert uitsluitend Streamable HTTP, niet het oude SSE transport.

---

## Features

- 🔍 **SearXNG-powered web search** met categorieën: `general`, `images`, `videos`, `files`, `map`, `social media`, `news`, `it`, `science`
- 📄 **Website scraping** met Trafilatura, citatie-metadata, en automatische Reddit URL conversie (`old.reddit.com`)
- 📜 **PDF naar Markdown** conversie via PyMuPDF / PyMuPDF4LLM
- 💾 **In-memory caching** met TTL en freshness validatie
- 🚦 **Domein-gebaseerde rate limiting**
- 🕒 **Timezone-aware** datum/tijd tool
- 🐳 **Docker + Docker Compose** ready
- 🔧 **Configureerbaar** via environment variables of `.env` bestand

---

## Quick Start

### 1. Clone en configureer

```bash
git clone <deze-repo>
cd mcp-searxng-enhanced
cp .env.example .env
# Bewerk .env en pas SEARXNG_ENGINE_API_BASE_URL aan!
```

### 2. Docker Compose (aanbevolen voor HTTP mode)

```bash
docker compose up --build
```

De server draait dan op `http://localhost:8000/mcp`.

### 3. Docker run (stdio mode — voor MCP clients zoals Cline)

```bash
docker build -t mcp-searxng-enhanced .
docker run -i --rm --network=host \
  -e SEARXNG_ENGINE_API_BASE_URL=http://127.0.0.1:8080/search \
  -e DESIRED_TIMEZONE=Europe/Amsterdam \
  mcp-searxng-enhanced
```

### 4. Native (zonder Docker)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python mcp_server.py
```

---

## Transport Modes

Stel in via de environment variable `MCP_TRANSPORT`:

| Mode | Waarde | Gebruik |
|------|--------|---------|
| **stdio** | `stdio` | MCP clients starten de server als subprocess (Claude, Cline, Cursor) |
| **Streamable HTTP** | `streamable-http` | De server luistert op een HTTP endpoint; clients verbinden via URL |
| **Both** | `both` | Stdio + HTTP tegelijk (handig voor debugging) |

### HTTP Mode details

Wanneer `MCP_TRANSPORT=streamable-http`:

- Endpoint: `http://localhost:8000/mcp` (standaard)
- Configureerbaar via `MCP_HTTP_HOST`, `MCP_HTTP_PORT`, `MCP_HTTP_PATH`
- Gebruikt **Streamable HTTP** per MCP protocol 2025-03-26
- Stateless by default (`stateless_http=True`)

### MCP Client configuratie

**stdio mode** (Cline / VS Code):
```json
{
  "mcpServers": {
    "searxng": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm", "--network=host",
        "-e", "SEARXNG_ENGINE_API_BASE_URL=http://host.docker.internal:8080/search",
        "-e", "DESIRED_TIMEZONE=Europe/Amsterdam",
        "mcp-searxng-enhanced:latest"
      ],
      "timeout": 120
    }
  }
}
```

**HTTP mode** (clients die HTTP MCP ondersteunen):
```json
{
  "mcpServers": {
    "searxng": {
      "url": "http://localhost:8000/mcp",
      "timeout": 120
    }
  }
}
```

---

## Environment Variables

| Variable | Standaard | Omschrijving |
|----------|-----------|--------------|
| `MCP_TRANSPORT` | `stdio` | Transport mode: `stdio`, `streamable-http`, `both` |
| `MCP_HTTP_HOST` | `0.0.0.0` | HTTP bind adres |
| `MCP_HTTP_PORT` | `8000` | HTTP poort |
| `MCP_HTTP_PATH` | `/mcp` | HTTP endpoint path |
| `SEARXNG_ENGINE_API_BASE_URL` | `http://host.docker.internal:8080/search` | **Verplicht:** je SearXNG endpoint |
| `DESIRED_TIMEZONE` | `Europe/Amsterdam` | Tijdzone voor datum/tijd tool |
| `RETURNED_SCRAPPED_PAGES_NO` | `3` | Max pagina's teruggegeven per zoekopdracht |
| `SCRAPPED_PAGES_NO` | `5` | Max pagina's geprobeerd te scrapen |
| `PAGE_CONTENT_WORDS_LIMIT` | `5000` | Max woorden per gescrapete pagina |
| `CITATION_LINKS` | `True` | Citaties genereren |
| `TRAFILATURA_TIMEOUT` | `15` | Content extractie timeout (sec) |
| `SCRAPING_TIMEOUT` | `20` | HTTP request timeout (sec) |
| `CACHE_MAXSIZE` | `100` | Max cache entries |
| `CACHE_TTL_MINUTES` | `5` | Cache TTL |
| `CACHE_MAX_AGE_MINUTES` | `30` | Max leeftijd cache voor validatie |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `10` | Max requests per domein per minuut |
| `RATE_LIMIT_TIMEOUT_SECONDS` | `60` | Rate limit venster |
| `MAX_IMAGE_RESULTS` | `10` | Max afbeeldingen |
| `MAX_VIDEO_RESULTS` | `10` | Max video's |
| `MAX_FILE_RESULTS` | `5` | Max bestanden |
| `MAX_MAP_RESULTS` | `5` | Max kaartresultaten |
| `MAX_SOCIAL_RESULTS` | `5` | Max social media resultaten |
| `IGNORED_WEBSITES` | `""` | Comma-separated domeinen om te negeren |

---

## Tools

| Tool | Beschrijving | Aliases |
|------|-------------|---------|
| `search_web` | Web search via SearXNG | `search`, `web_search`, `find` |
| `get_website` | Scrape website of PDF | `fetch_url`, `scrape_page` |
| `get_current_datetime` | Huidige datum/tijd | `current_time`, `get_time` |

### Voorbeelden

**Zoeken:**
```json
{ "name": "search_web", "arguments": { "query": "quantum computing" } }
```

**Afbeeldingen:**
```json
{ "name": "search_web", "arguments": { "query": "zonsondergang", "category": "images" } }
```

**Website scrapen:**
```json
{ "name": "get_website", "arguments": { "url": "https://example.com" } }
```

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  MCP Client     │────▶│  mcp_server.py   │────▶│   SearXNG   │
│  (Claude/etc)   │     │  FastMCP         │     │   Instance  │
└─────────────────┘     └──────────────────┘     └─────────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │  Websites   │
                        │  (scraping) │
                        └─────────────┘
```

- **Transport laag**: MCP Python SDK (`FastMCP`) handelt stdio of Streamable HTTP af
- **Business logica**: Herbruikbare async functies voor search, scrape, cache
- **Configuratie**: Pydantic v2 model met env-var override

---

## Troubleshooting

| Probleem | Oplossing |
|----------|-----------|
| Kan geen verbinding maken met SearXNG | Controleer `SEARXNG_ENGINE_API_BASE_URL` en of SearXNG draait |
| HTTP mode start niet | Controleer of poort 8000 vrij is; pas `MCP_HTTP_PORT` aan |
| Rate limit errors | Verhoog `RATE_LIMIT_REQUESTS_PER_MINUTE` |
| Traag scrapen | Verhoog `TRAFILATURA_TIMEOUT` en `SCRAPING_TIMEOUT` |
| Docker networking (Linux) | Gebruik `--network=host` of het host IP adres |

---

## License

MIT License © 2025 — Origineel door OvertliDS, HTTP fork door community.

---

## Waarom geen SSE meer?

MCP protocol 2024-11-05 definieerde een **HTTP+SSE transport** waarbij clients een SSE stream openden voor server→client berichten en POST gebruikten voor client→server. Dit is **vervangen** door **Streamable HTTP** in protocol 2025-03-26. Streamable HTTP is schaalbaarder, stateless-compatible, en kan optioneel SSE gebruiken voor streaming binnen hetzelfde endpoint — maar vereist geen aparte SSE verbinding meer.

> Deze server implementeert **uitsluitend** het huidige Streamable HTTP transport. Geen legacy SSE.
