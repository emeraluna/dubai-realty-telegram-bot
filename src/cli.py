from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from config import configure_logging, get_settings
from db.repository import ListingRepository
from db.session import session_scope
from importers.owner_importer import import_owner_file
from services.owner_resolve_pipeline import resolve_owner_for_input


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cli")
    sub = parser.add_subparsers(dest="command", required=True)

    import_cmd = sub.add_parser("import-owners", help="Import owner records from CSV/XLSX/XLS")
    import_cmd.add_argument("path", type=Path)
    import_cmd.add_argument("--mapping", type=Path, help="JSON header override mapping")
    import_cmd.add_argument("--admin-id", type=int, default=0, help="Admin user id for audit")
    resolve_cmd = sub.add_parser("resolve-owner", help="Long-running automated owner resolution")
    phone_cmd = sub.add_parser("resolve-dld-phone", help="Resolve owner via DLD-registered mobile")
    phone_cmd.add_argument("phone", help="UAE mobile e.g. +971521149496")
    resolve_cmd.add_argument("input", help="PF/Bayut URL, Trakheesi permit, or DLD mobile")
    return parser


async def _run_import(path: Path, mapping: Path | None, admin_id: int) -> int:
    override = None
    if mapping:
        override = json.loads(mapping.read_text(encoding="utf-8"))
    result = await import_owner_file(path, admin_user_id=admin_id, mapping_override=override)
    print(result.summary_line())
    if result.warnings:
        for warning in result.warnings:
            print(f"warning: {warning}")
    if result.error_report_csv:
        out = path.with_suffix(path.suffix + ".errors.csv")
        out.write_bytes(result.error_report_csv)
        print(f"errors written: {out}")
    return 0


async def _run_resolve_dld_phone(phone: str) -> int:
    return await _run_resolve_owner(phone)


async def _run_resolve_owner(text: str) -> int:
    settings = get_settings()
    async with session_scope() as session:
        repo = ListingRepository(session, cache_ttl_days=settings.cache_ttl_days)
        outcome = await resolve_owner_for_input(repo, text)
    if outcome.listing is None:
        print(outcome.message)
        return 1
    print(
        f"success={outcome.success} attempts={outcome.attempts} "
        f"owner_name={outcome.listing.owner_name} owner_phone={outcome.listing.owner_phone}"
    )
    return 0 if outcome.success else 2


def main(argv: list[str] | None = None) -> None:
    configure_logging(get_settings().log_level)
    args = _build_parser().parse_args(argv)
    if args.command == "import-owners":
        code = asyncio.run(_run_import(args.path, args.mapping, args.admin_id))
        sys.exit(code)
    if args.command == "resolve-owner":
        code = asyncio.run(_run_resolve_owner(args.input))
        sys.exit(code)
    if args.command == "resolve-dld-phone":
        code = asyncio.run(_run_resolve_dld_phone(args.phone))
        sys.exit(code)
    sys.exit(1)


if __name__ == "__main__":
    main()