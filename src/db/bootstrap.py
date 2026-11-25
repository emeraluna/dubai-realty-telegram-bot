from __future__ import annotations

from pathlib import Path

import structlog
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from db.session import dispose_engine, get_engine

log = structlog.get_logger(__name__)


def _alembic_config() -> Config:
    candidates = [
        Path("alembic.ini"),
        Path(__file__).resolve().parents[2] / "alembic.ini",
    ]
    for path in candidates:
        if path.is_file():
            return Config(str(path))
    raise FileNotFoundError("alembic.ini not found")


def run_migrations() -> None:
    cfg = _alembic_config()
    log.info("db.migrate.start")
    command.upgrade(cfg, "head")
    log.info("db.migrate.done")


async def verify_database() -> None:
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    log.info("db.connection.ok")