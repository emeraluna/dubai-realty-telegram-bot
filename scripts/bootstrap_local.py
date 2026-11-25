"""Initialize data/, .env (from example), SQLite DBs, and alembic schema."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SRC = ROOT / "src"
ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"


def _posix_path(path: Path) -> str:
    return path.resolve().as_posix()


def ensure_env() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    if ENV.is_file():
        print(".env exists — leaving unchanged")
        return
    if not EXAMPLE.is_file():
        raise SystemExit(".env.example missing")
    shutil.copy(EXAMPLE, ENV)
    realty_db = _posix_path(DATA / "realty.db")
    dld_db = _posix_path(DATA / "dld_owners.sqlite")
    lines = ENV.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for line in lines:
        if line.startswith("DATABASE_URL="):
            out.append(f"DATABASE_URL=sqlite+aiosqlite:///{realty_db}")
        elif line.startswith("DLD_OWNER_DATABASE_URL="):
            out.append(f"DLD_OWNER_DATABASE_URL=sqlite+aiosqlite:///{dld_db}")
        else:
            out.append(line)
    ENV.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {ENV}")


def pip_install() -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", ".[dev]"], cwd=ROOT)


def migrate() -> None:
    os.environ.setdefault("PYTHONPATH", str(SRC))
    if SRC.is_dir() and str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    from db.bootstrap import run_migrations

    run_migrations()


def seed_dld() -> None:
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "seed_dld_owner_db.py")], cwd=ROOT)


def main() -> int:
    ensure_env()
    pip_install()
    migrate()
    seed_dld()
    print("bootstrap complete — set TELEGRAM_BOT_TOKEN in .env then: python -m bot.main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())