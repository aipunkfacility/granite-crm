# Granite CRM — Context for Qwen Code

## Project Overview

**Granite CRM** is a Python-based pipeline for scraping, deduplicating, enriching, and managing a database of granite memorial workshops and monument manufacturers across Russia. It combines:

1. **Data Pipeline** — multi-phase ETL pipeline that scrapes sources (jsprav.ru, DuckDuckGo, 2GIS, Yell), deduplicates records, enriches with messenger links (Telegram, WhatsApp, VK), CMS detection, and scores companies.
2. **FastAPI CRM Backend** — REST API for managing the enriched companies, CRM contacts, tasks, email campaigns, and funnel tracking.

The project targets Windows (win32), uses SQLite with WAL mode, and is managed with `uv` as the package manager.

**Tech Stack:** Python 3.12+, SQLAlchemy 2.x, Alembic, FastAPI, Pydantic, httpx, Crawlee, Playwright, BeautifulSoup4, RapidFuzz, loguru, Typer CLI.

## Key Directories and Files

```
granite-crm-db/
├── cli.py                      # Typer CLI entry point (run, export, db migrations, api)
├── config.yaml                 # Cities, sources, scoring, enrichment settings
├── pyproject.toml              # Dependencies (uv-managed)
├── requirements.txt            # Legacy pip requirements
├── main.py                     # Alternative entry point
├── AGENTS.md                   # Agent development standards (Russian)
├── granite/
│   ├── database.py             # ORM models + Database class (SQLite WAL, Alembic)
│   ├── models.py               # Pydantic data models
│   ├── utils.py                # Transliteration, phone normalization, HTTP helpers
│   ├── regions.py              # Region → city mapping resolver
│   ├── category_finder.py      # Auto-discovery of jsprav.ru subdomains/categories
│   ├── http_client.py          # Singleton async HTTP client (httpx.AsyncClient)
│   ├── config_validator.py     # Config.yaml validation at startup
│   ├── api/                    # FastAPI CRM REST API
│   │   ├── app.py              # FastAPI app with lifespan, CORS, router includes
│   │   ├── deps.py             # get_db dependency (session per request)
│   │   ├── schemas.py          # Pydantic request/response schemas
│   │   ├── companies.py        # Companies CRUD + filtering + pagination
│   │   ├── touches.py          # Contact touch logging (email, TG, WA)
│   │   ├── tasks.py            # Task management
│   │   ├── tracking.py         # Email tracking pixel + open detection
│   │   ├── campaigns.py        # Email campaign management
│   │   ├── followup.py         # Automated follow-up logic
│   │   ├── funnel.py           # Funnel stage transitions
│   │   └── messenger.py        # Messenger (TG/WA) sending endpoints
│   ├── scrapers/               # Data source scrapers
│   │   ├── base.py             # BaseScraper interface
│   │   ├── jsprav.py           # Jsprav.ru (JSON-LD, primary source)
│   │   ├── jsprav_playwright.py# Jsprav.ru Playwright fallback
│   │   ├── web_search.py       # DuckDuckGo web search scraper
│   │   ├── dgis.py             # 2GIS (Crawlee + API, disabled by default)
│   │   └── yell.py             # Yell.ru (Crawlee Playwright, disabled by default)
│   ├── enrichers/              # Data enrichment modules
│   │   ├── messenger_scanner.py# Parse messengers from HTML (TG, WA, VK)
│   │   ├── tg_finder.py        # Find Telegram by phone/name
│   │   ├── tg_trust.py         # Telegram profile trust scoring
│   │   ├── tech_extractor.py   # CMS detection (Bitrix, WordPress, Tilda...)
│   │   ├── classifier.py       # CRM scoring and segmentation (A/B/C/D)
│   │   ├── network_detector.py # Detect franchise/branch networks
│   │   └── reverse_lookup.py   # Reverse lookup in 2GIS/Yell for sparse companies
│   ├── dedup/                  # Deduplication modules
│   │   ├── phone_cluster.py    # Phone-based clustering (Union-Find)
│   │   ├── name_matcher.py     # Fuzzy name matching (RapidFuzz)
│   │   ├── site_matcher.py     # Domain-based matching
│   │   └── merger.py           # Record merging + conflict resolution
│   ├── pipeline/               # ETL pipeline phases
│   │   ├── manager.py          # Pipeline orchestrator (~60 lines, delegates to phases)
│   │   ├── scraping_phase.py   # Phase 1: Multi-source scraping
│   │   ├── dedup_phase.py      # Phase 2: Deduplication (Union-Find)
│   │   ├── enrichment_phase.py # Phase 3: Enrichment (sync ThreadPool / async httpx)
│   │   ├── scoring_phase.py    # Phase 5: Scoring & segmentation
│   │   ├── export_phase.py     # Phase 6: CSV/Markdown export + presets
│   │   ├── checkpoint.py       # Resume from interrupted phase
│   │   ├── region_resolver.py  # City → region resolution
│   │   ├── web_client.py       # WebClient: search + scrape (sync)
│   │   └── status.py           # Rich console status printing
│   ├── exporters/              # Data export
│   │   ├── csv.py              # CSV export (UTF-8 BOM, presets)
│   │   └── markdown.py         # Markdown export
│   ├── email/                  # Email sending/tracking (CRM)
│   └── messenger/              # Messenger sending (TG/WA)
├── alembic/
│   ├── env.py                  # Alembic migration environment
│   └── versions/               # Migration files (3 migrations: initial, drop pipeline_runs, add CRM tables)
├── tests/                      # Pytest test suite
├── data/
│   ├── granite.db              # SQLite database (~6000 companies, 29 cities)
│   ├── regions.yaml            # 40 regions, 566 cities directory
│   ├── category_cache.yaml     # Cached jsprav subdomains/categories
│   ├── logs/granite.log        # Rotating log (10 MB)
│   └── export/                 # Exported CSV/MD files
└── scripts/
    └── benchmark.py            # Sync vs async enrichment benchmark
```

## Database Schema

SQLite with WAL mode, managed by Alembic. Key tables:

| Table | Purpose |
|-------|---------|
| `raw_companies` | Raw scraped data (source, name, phones, website, emails, city) |
| `companies` | Deduplicated unique records (merged_from, name_best, phones, website) |
| `enriched_companies` | Enriched data (messengers, tg_trust, cms, crm_score, segment, is_network) — 1:1 FK to companies |
| `crm_contacts` | CRM funnel state (funnel_stage, email/TG/WA metrics, notes, stop_automation) |
| `crm_touches` | Contact touch log (channel, direction, subject, body) |
| `crm_templates` | Message templates with {placeholder} substitution |
| `crm_email_logs` | Email send log with tracking UUID for open pixel |
| `crm_tasks` | Tasks (follow-up, portfolio, call) |
| `crm_email_campaigns` | Email campaign definitions + stats |

### ORM Models (database.py)

- `RawCompanyRow` — raw scraped entries
- `CompanyRow` — deduplicated companies
- `EnrichedCompanyRow` — enriched company data (1:1 FK to CompanyRow)
- `CrmContactRow` — CRM contact (funnel stage, metrics)
- `CrmTouchRow` — contact touch log
- `CrmTemplateRow` — message templates
- `CrmEmailLogRow` — email send/open tracking
- `CrmTaskRow` — tasks
- `CrmEmailCampaignRow` — email campaigns

## Pipeline Flow

```
run "City"
  → ScrapingPhase: jsprav + web_search → raw_companies
  → DedupPhase: Union-Find by phone/site → companies
  → EnrichmentPhase: messengers, TG finder, CMS → enriched_companies
  → Reverse Lookup (optional): 2GIS/Yell for sparse records
  → NetworkDetector: find franchise networks
  → ScoringPhase: CRM scoring (A≥50, B≥30, C≥15, D)
  → ExportPhase: CSV + preset exports
```

### Checkpoint System

The pipeline remembers progress via checkpoint stages: `start → scraped → deduped → enriched`. Flags:

- `--force` — clear all data, start from scratch
- `--no-scrape` — skip scraping, start from dedup
- `--re-enrich` — skip scrape+dedup, run deep enrichment only

## Key Commands

### Package Management (uv)

```bash
uv add <package>          # Add dependency
uv remove <package>       # Remove dependency
uv sync                   # Sync environment
uv run <script>           # Run script with project deps
```

### CLI (cli.py via typer)

```bash
# Pipeline
python cli.py run "City"              # Run full pipeline for a city
python cli.py run "City" --force      # Force clean start
python cli.py run "City" --no-scrape  # Skip scraping
python cli.py run "City" --re-enrich  # Re-enrich only
python cli.py run all                 # Run all cities from config

# Export
python cli.py export "City" --format csv
python cli.py export "City" --format md
python cli.py export-preset "City" hot_leads

# API Server
python cli.py api --port 8000
python cli.py api --port 8000 --reload

# Database Migrations (Alembic)
python cli.py db check                # Check if migration needed
python cli.py db migrate "description" # Create migration
python cli.py db upgrade head         # Apply migrations
python cli.py db downgrade -1         # Rollback one version
python cli.py db history -v           # Migration history
python cli.py db current              # Current schema version
python cli.py db stamp head           # Stamp existing DB as current
```

### Testing

```bash
python -m pytest tests/ -v                    # All tests
python -m pytest tests/test_migrations.py -v  # Migration tests
python -m pytest tests/test_crm_api.py -v     # API tests
python -m pytest tests/test_enrichers.py -v   # Enricher tests
python -m pytest -k "async" -v                # Async tests only
```

## Development Conventions

### Database Sessions

Always use `session_scope()` context manager for safe DB operations:

```python
with db.session_scope() as session:
    companies = session.query(CompanyRow).filter_by(city=city).all()
```

Never call `session.commit()` inside `session_scope()` — it auto-commits on exit.

### HTTP Requests

- All external URLs must pass `is_safe_url()` check (SSRF protection)
- Log URLs via `_sanitize_url_for_log()` — never log raw URLs (may contain PII)
- Timeout: 15s default, 8s for batch scraping
- `fetch_page()` already has retry via tenacity — don't wrap additionally

### Async vs Sync

- `config.enrichment.async_enabled: true` → `http_client.py` (httpx.AsyncClient)
- Otherwise → ThreadPoolExecutor in `_enrich_companies_parallel()`
- Don't mix sync and async without `run_async()` from `http_client.py`

### Code Style

- Type hints on all functions — mandatory
- Docstrings on public methods (what it does, what it returns, what it raises)
- Max line length: 100 characters
- Import order: stdlib → third-party → local (`granite.*`)

### Schema Changes

Always through Alembic — never direct SQL:

1. Modify ORM model in `granite/database.py`
2. `python cli.py db check` — verify Alembic detects changes
3. `python cli.py db migrate "description"` — create migration
4. Review generated file in `alembic/versions/`
5. `python cli.py db upgrade head` — apply

### Security

- `is_safe_url()` — check ALL external URLs before HTTP requests
- SQL: no f-strings in queries. Escape `%` and `_` in `ilike`:

  ```python
  def _escape_like(s: str) -> str:
      return s.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
  ```

- Secrets (API keys) — only via `.env` / environment variables, never in `config.yaml`

## Config Structure (config.yaml)

- `cities` — list of cities with name, population, region, status, geo_center
- `scraping` — global scraping settings (delays, timeouts, threads)
- `sources` — per-source config (enabled, categories, subdomains)
- `crawlee` — Crawlee settings (session pool, proxy)
- `dedup` — deduplication settings (threshold, auto-merge)
- `enrichment` — enrichment settings (web_client, async_enabled, tg_finder, reverse_lookup)
- `scoring.weights` — points per feature (has_telegram: 15, has_website: 5, etc.)
- `scoring.levels` — segment thresholds (A≥50, B≥30, C≥15)
- `export_presets` — preset filters (hot_leads, with_telegram, cold_email, etc.)
- `logging` — log level, rotation, format
- `database` — SQLite path

## Scoring Weights

| Parameter | Points | Description |
|-----------|--------|-------------|
| has_telegram | +15 | Telegram found |
| has_whatsapp | +10 | WhatsApp found |
| has_website | +5 | Website exists |
| has_email | +5 | Email exists |
| cms_bitrix | +10 | Site on Bitrix |
| cms_modern | +3 | Site on WordPress/Tilda |
| has_marquiz | +8 | Marquiz widget on site |
| multiple_phones | +5 | More than one phone |
| is_network | +5 | Part of franchise network |
| tg_trust_multiplier | ×2 | Multiplier for live TG profile (trust_score ≥ 2) |

## Common Pitfalls (Don't Do These)

1. Don't read `r.phones`/`r.emails` in threads without eager loading — SQLAlchemy lazy load is not thread-safe
2. Don't hardcode 15s timeout everywhere — jsprav detail pages need 8s
3. Don't use bare `except Exception:` — at minimum log error category via `_classify_error()`
4. Don't change `config.yaml` during pipeline execution — it's read once at startup
5. Don't run `DROP TABLE` via SQLite MCP — use `python cli.py run "City" --force`
6. Don't use `pip install` — only `uv add`

## Related Projects

- **Granite Web UI** — Next.js frontend, TypeScript, shadcn/ui, TanStack Query v5 (separate repository)
- **Related agent skill:** Data Auditor (project), github (project), notebooklm (project)
