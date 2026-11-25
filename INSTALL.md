# Install on a new machine

Copy the whole project folder to the target PC (USB, zip, git clone). No pre-installed database server is required for the default **SQLite** layout.

## Prerequisites

- **Python 3.11+** on `PATH` (`python` / `python3`)
- **Telegram bot token** ([@BotFather](https://t.me/BotFather))
- Optional: Apify / ScrapeForge keys, DLD session JWT, `CAPTCHA_API_KEY` for live Madmoun

## Windows (recommended)

```powershell
cd path\to\project
.\setup.ps1
notepad .env
python -m bot.main
```

`setup.ps1` runs `scripts/bootstrap_local.py`: creates `data/`, copies `.env.example` → `.env` with SQLite URLs, `pip install -e ".[dev]"`, Alembic migrate, seeds empty `dld_owners.sqlite`.

## Linux / macOS

```bash
cd path/to/project
chmod +x setup.sh
./setup.sh
nano .env
python3 -m bot.main
```

## Docker (Postgres)

```bash
cp .env.example .env
# set TELEGRAM_BOT_TOKEN; DATABASE_URL is overridden in compose for Postgres
docker compose up -d --build
docker compose logs -f app
```

Postgres data lives in the `pgdata` volume. App runs migrations on start.

## Verify install

```bash
python scripts/check_env.py
python -m pytest -q
```

## CLI (no Telegram)

```bash
python -m cli import-owners examples/owners_sample.csv --admin-id 1
python -m cli resolve-owner "https://www.propertyfinder.ae/en/plp/buy/....html"
python -m cli resolve-dld-phone +971521149496
python scripts/resolve_pf_url.py "<PF URL>"
```

## Operator data files

| Path | Purpose |
|------|---------|
| `data/realty.db` | Bot listing archive (created on migrate) |
| `data/dld_owners.sqlite` | Local DLD owner mirror (`seed_dld_owner_db.py`) |
| `data/owner_registry.csv` | Manual owner rows (ad_license / phone / guid) |
| `data/madmoun_*.json` | Cached Trakheesi integration JSON |

## Production env (minimal)

```env
TELEGRAM_BOT_TOKEN=
DATABASE_URL=sqlite+aiosqlite:///ABS/PATH/data/realty.db
APIFY_TOKEN=
APIFY_ACTOR_PROPERTYFINDER=
SCRAPEFORGE_KEY=
SCRAPEFORGE_BASE_URL=
EXTRACTOR_PRIORITY_PROPERTYFINDER=propertyfinder_api,direct
DLD_OWNER_DATABASE_URL=sqlite+aiosqlite:///ABS/PATH/data/dld_owners.sqlite
ALLOWED_TELEGRAM_IDS=
IMPORT_ADMIN_IDS=
```

Use absolute paths in `DATABASE_URL` on Windows (`E:/app/data/realty.db`).

## Upgrade on an existing copy

```bash
pip install -e ".[dev]"
alembic upgrade head
```