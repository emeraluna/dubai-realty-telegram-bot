# Project layout

```
dubai-realty-bot/
├── INSTALL.md              # Deploy on a new machine
├── setup.ps1 / setup.sh    # One-shot bootstrap
├── pyproject.toml          # Package + deps (pip install -e .)
├── alembic/                # DB migrations
├── src/
│   ├── bot/                # aiogram v3 handlers, worker
│   ├── cli.py              # import-owners, resolve-owner, resolve-dld-phone
│   ├── config/             # pydantic-settings
│   ├── db/                 # models, repository, session
│   ├── importers/          # CSV/XLSX owner import (Phase 9)
│   ├── scrapers/           # PF/Bayut/DLD/Madmoun extractors
│   └── services/           # resolve pipeline, registry, phone lookup
├── scripts/                # Ops CLI (see scripts/README.md)
│   └── dev/                # R&D probes (not required for production)
├── data/                   # SQLite DBs + registry CSV (runtime)
├── examples/               # Sample owner import files
└── tests/                  # pytest suite
```