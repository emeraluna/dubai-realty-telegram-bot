# Runtime data (created on bootstrap)

| File | Notes |
|------|--------|
| `realty.db` | Main bot DB (listings, lookups, imports) — not committed |
| `dld_owners.sqlite` | Operator DLD owner export mirror |
| `owner_registry.csv` | Committed template; fill `owner_name` / `owner_phone` rows |
| `madmoun_*.json` | Optional Trakheesi integration cache per listing |

Copy this folder with the project or let `setup.ps1` / `bootstrap_local.py` recreate empty DBs.