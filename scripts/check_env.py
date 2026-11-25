from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _try_import(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


async def _db_reachable(url: str) -> tuple[bool, str]:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with asyncio.timeout(3):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return True, "PASS"
    except Exception as exc:
        return False, f"WARN ({exc})"
    finally:
        await engine.dispose()


def main() -> int:
    py_ok = sys.version_info >= (3, 11)
    print(f"Python >= 3.11: {_status(py_ok)} ({sys.version.split()[0]})")

    packages = ("aiogram", "httpx", "sqlalchemy", "pydantic", "pandas", "openpyxl")
    pkg_ok = True
    for name in packages:
        ok = _try_import(name)
        pkg_ok = pkg_ok and ok
        print(f"import {name}: {_status(ok)}")

    try:
        from config import get_settings

        settings = get_settings()
        tg = bool(settings.telegram_bot_token.strip())
        apify = bool(settings.apify_token.strip())
        sf = bool(settings.scrapeforge_key.strip())
        db_set = bool(settings.database_url.strip())
    except Exception as exc:
        print(f"settings: FAIL ({exc})")
        return 1

    print(f"TELEGRAM_BOT_TOKEN present: {_status(tg)}")
    print(f"APIFY_TOKEN present (optional if direct/PF API): {_status(apify)}")
    print(f"SCRAPEFORGE_KEY present (optional): {_status(sf)}")
    print(f"DATABASE_URL present: {_status(db_set)}")

    if db_set:
        _, label = asyncio.run(_db_reachable(settings.database_url))
        print(f"DATABASE_URL reachable: {label}")
    else:
        print("DATABASE_URL reachable: WARN (not configured)")

    required_ok = py_ok and pkg_ok and db_set
    return 0 if required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())