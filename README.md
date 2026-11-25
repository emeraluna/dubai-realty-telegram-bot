# dubai-realty-bot

Private Telegram bot for Dubai Property Finder / Bayut URLs, Trakheesi permits, and DLD-registered mobiles. Extracts listing + permit metadata, resolves legal owner when your sources provide it (registry, DLD DB export, authenticated APIs), caches every lookup.

## Copy to another PC

1. Copy the **entire project folder** (include `src/`, `alembic/`, `data/owner_registry.csv`, `examples/`, not `.env` secrets).
2. Follow **[INSTALL.md](INSTALL.md)** — Windows: `.\setup.ps1`; Linux: `./setup.sh`.
3. Set `TELEGRAM_BOT_TOKEN` in `.env`, run `python -m bot.main`.

Default install uses **SQLite** under `data/` (no Postgres install required). Use `docker compose up` for Postgres or `docker compose -f docker-compose.sqlite.yml up` for container + SQLite volume.

## Requirements

- Python 3.11+
- Docker + Docker Compose (optional)
- Telegram bot token ([@BotFather](https://t.me/BotFather))
- Apify / ScrapeForge optional; `propertyfinder_api` + `direct` work without them

## Environment variables

Copy `.env.example` to `.env` and set values:

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | yes | Bot token from BotFather |
| `APIFY_TOKEN` | yes* | Apify API token |
| `APIFY_ACTOR_PROPERTYFINDER` | yes* | Apify actor ID for Property Finder |
| `APIFY_ACTOR_BAYUT` | yes* | Apify actor ID for Bayut |
| `SCRAPEFORGE_KEY` | yes* | ScrapeForge API key |
| `SCRAPEFORGE_BASE_URL` | yes* | ScrapeForge API base URL |
| `DATABASE_URL` | yes | Async SQLAlchemy URL (`postgresql+asyncpg://...`) |
| `ALLOWED_TELEGRAM_IDS` | no | Comma-separated Telegram user IDs; empty = allow all |
| `CACHE_TTL_DAYS` | no | Days before re-extracting a listing (default `30`) |
| `LOG_LEVEL` | no | `INFO`, `DEBUG`, etc. |
| `TRAKHEESI_PERMIT_MIN_LENGTH` | no | Min permit digits (default `10`) |
| `TRAKHEESI_PERMIT_MAX_LENGTH` | no | Max permit digits (default `15`) |
| `DLD_PERMIT_API_URL` | no | DLD public permit API base URL |
| `EXTRACTOR_PRIORITY_PROPERTYFINDER` | no | Comma list: `apify,scrapeforge,direct` |
| `EXTRACTOR_PRIORITY_BAYUT` | no | Comma list: `apify,scrapeforge,direct` |
| `EXTRACTOR_PRIORITY_TRAKHEESI` | no | Default `trakheesi` |
| `EXTRACTOR_CONCURRENCY_*` | no | Per-source asyncio limits |

\*At least one extractor path must work for listing URLs: configure Apify actors and/or ScrapeForge, or rely on `direct` (public page parse) in the priority list.

## Apify keys and actors

1. Create an account at [apify.com](https://apify.com).
2. Open **Settings → Integrations → API tokens** and create a token → set `APIFY_TOKEN`.
3. In **Apify Store**, add actors that scrape Property Finder and Bayut (or use your own).
4. Copy each actor’s ID from the actor URL (`apify.com/.../acts/<ACTOR_ID>`) into:
   - `APIFY_ACTOR_PROPERTYFINDER`
   - `APIFY_ACTOR_BAYUT`
5. Actor output should include listing fields and contact aliases (`ownerName`, `contactPhone`, `mobile`, etc.) — mapped in `src/scrapers/actor_maps.py`.

## ScrapeForge keys

1. Obtain API base URL and key from your ScrapeForge (or compatible) dashboard.
2. Set `SCRAPEFORGE_BASE_URL` (no trailing slash) and `SCRAPEFORGE_KEY`.
3. Listing endpoint used: `POST {SCRAPEFORGE_BASE_URL}/v1/scrape/listing` with JSON `source`, `url`, `listing_id`.

## First run (local)

```bash
# Windows: .\setup.ps1
# Linux:   ./setup.sh
# or:      make bootstrap

# edit .env — TELEGRAM_BOT_TOKEN required
python -m bot.main
```

## First run (Docker Compose)

```bash
cp .env.example .env
# edit .env

make up
make logs
```

`docker compose up` starts Postgres, waits for health, runs `alembic upgrade head`, then starts the bot (`scripts/docker-entrypoint.sh`). Local `python -m bot.main` also runs migrations via `run_migrations()` before polling.

## Example inputs (send as a private message)

**Property Finder URL**

```text
https://www.propertyfinder.ae/en/plp/buy/apartment-for-sale-dubai-marina-12345678.html
```

**Bayut URL**

```text
https://www.bayut.com/property/details-9876543.html
```

**Trakheesi permit**

```text
7123456789012
```

or

```text
permit:7123456789012
```

## Bot commands

- `/start` — welcome
- `/help` — usage
- `/export` — CSV of listings you have looked up
- `/stats` — lookups, cache hits, savings

Inline buttons after a lookup: **Refresh** (force re-extract), **Export this record**.

## Development

```bash
make test    # pytest
make lint    # ruff + mypy
make down    # stop compose stack
```

## Owner contact behavior

Extraction maps owner name/phone from Apify, ScrapeForge, direct page JSON (`__NEXT_DATA__` / JSON-LD), and DLD permit responses. The bot always persists the listing; if contact fields are missing after the extractor chain merge, the reply shows `owner contact not available from source`.

## Excel / CSV owner import

Bulk import or update owner and listing fields from `.csv`, `.xlsx`, or `.xls`.

### Config

- `IMPORT_ADMIN_IDS` — comma-separated Telegram user IDs allowed to run `/import` and upload files (required; import is refused when empty).
- `IMPORT_FUZZY_THRESHOLD` — fuzzy header match threshold (default `85`).

### Telegram

- `/import` — bot asks for a spreadsheet.
- Upload `.csv` / `.xlsx` / `.xls` — summary: `Rows | Inserted | Updated | Skipped | Errors`, with **Download error report** when errors &gt; 0.
- `/imports` — last 10 `ImportBatch` rows with counts.

### CLI

```bash
python -m cli import-owners examples/owners_sample.csv --admin-id 1
python -m cli import-owners examples/owners_sample.xlsx --mapping mapping.json
```

### Accepted columns (aliases)

Canonical fields: `permit_number`, `source_listing_id`, `source_url`, `unit_number`, `floor`, `building`, `community`, `developer`, `size_sqft`, `plot_number`, `owner_name`, `owner_phone`.

Examples: `permit` / `trakheesi` → `permit_number`; `owner` / `landlord` → `owner_name`; `phone` / `mobile` → `owner_phone`; `url` / `link` → `source_url`.

### Row matching order

1. `permit_number`
2. `source_listing_id` (any known source)
3. `source_url`
4. `unit_number` + `building`

If no match, a new `Listing` is created with `source=manual` and `owner_source=manual`.

### Precedence vs scraped data

Manual import sets `owner_source=manual`. Subsequent scrapes **cannot overwrite** manual `owner_name` / `owner_phone`; scrapes may only fill those fields when blank. Non-owner fields on manual rows are updated on each manual import (last import wins). Scraped rows get `owner_source=scraped` when owner contact is present.

### Audit tables

- `ImportBatch` — one row per file (counts, filename, `errors` warnings JSON).
- `ImportRow` — one row per input line (`inserted` / `updated` / `skipped` / `error`, `matched_listing_id`, `raw_row`).

### Partial import recovery

Fix the spreadsheet and re-upload. Matching is idempotent: duplicate rows update or skip without creating duplicates. Download the error report CSV, correct flagged `row_index` values, and import again.

### Samples

- `examples/owners_sample.csv`
- `examples/owners_sample.xlsx`