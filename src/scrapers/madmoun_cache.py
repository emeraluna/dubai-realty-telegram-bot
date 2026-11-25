from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CACHE_DIR = _ROOT / "data"


@lru_cache(maxsize=32)
def load_cached_integration_by_guid(guid: str) -> dict | None:
    if not guid or not _CACHE_DIR.is_dir():
        return None
    for path in sorted(_CACHE_DIR.glob("madmoun_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        body = data.get("Response") or data.get("result") or data
        if not isinstance(body, dict):
            continue
        if body.get("ListingGuid") == guid or body.get("listingGuid") == guid:
            return data
        if guid in path.read_text(encoding="utf-8"):
            return data
    return None