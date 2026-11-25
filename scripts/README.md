# Scripts

## First-time / ops

| Script | Purpose |
|--------|---------|
| `bootstrap_local.py` | `.env`, SQLite paths, pip install, migrate, seed DLD DB |
| `check_env.py` | Dependency and settings smoke check |
| `seed_dld_owner_db.py` | Create `data/dld_owners.sqlite` schema |
| `import_madmoun_json.py` | Load integration JSON into listing `raw_payload` |
| `sync_listing_owner.py` | Madmoun JSON + owner resolve for a fixed listing |
| `run_owner_resolve_once.py` | One owner-resolve cycle (listing id=1) |
| `resolve_pf_url.py` | Extract + resolve from a PF URL |
| `resolve_dld_phone.py` | Owner lookup by UAE mobile |
| `local_setup_and_resolve.py` | Seed Binghatti sample + long resolve |
| `probe_apify_actor.py` | Test Apify actor against a URL |
| `probe_owner_endpoints.py` | Probe configured DLD HTTP templates |
| `discover_dld_paths.py` | Try public DLD path patterns |
| `test_extract.py` | Run extractor chain on one URL |

## Maintenance

| Script | Purpose |
|--------|---------|
| `_fix_listing_owner.py` | Clear placeholder / broker-as-owner rows |
| `_clear_placeholders.py` | Remove `REPLACE_*` owner fields |

## `dev/` (R&D only)

Underscore probes (`_madmoun_*`, `_find_*`, token/JS experiments). Not required to run the bot.