from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config import configure_logging, get_settings  # noqa: E402
from db.repository import ListingRepository  # noqa: E402
from db.session import dispose_engine, session_scope  # noqa: E402
from scrapers.chain import EXTRACTOR_REGISTRY, ExtractorChain  # noqa: E402
from scrapers.errors import ExtractionError  # noqa: E402
from scrapers.payload import ListingPayload  # noqa: E402
from services.input_parser import InputParseError, parse_lookup_input  # noqa: E402
from services.lookup_request import LookupRequest  # noqa: E402
from services.owner_enrichment import enrich_owner_from_dld  # noqa: E402

CHECKLIST_FIELDS = ("owner_name", "owner_phone", "permit_number", "building")

PAYLOAD_FIELDS = (
    "unit_number",
    "floor",
    "building",
    "community",
    "developer",
    "size_sqft",
    "plot_number",
    "permit_number",
    "permit_status",
    "owner_name",
    "owner_phone",
)


def _field_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def format_checklist_line(field: str, value: object) -> str:
    tag = "PASS" if _field_present(value) else "MISS"
    return f"[{tag}] {field}"


def format_checklist(payload: ListingPayload) -> list[str]:
    data = payload.model_dump()
    return [format_checklist_line(field, data.get(field)) for field in CHECKLIST_FIELDS]


def format_critical_owner_line(payload: ListingPayload) -> str | None:
    if not _field_present(payload.owner_name) and not _field_present(payload.owner_phone):
        return "MISSING CRITICAL: owner_contact"
    return None


def _req_line(req: LookupRequest) -> str:
    return f"LookupRequest(source={req.source!r}, external_id={req.external_id!r}, raw_input={req.raw_input!r})"


def _validate_extractor_tokens(extractor: str, req: LookupRequest) -> str | None:
    settings = get_settings()
    if extractor == "apify":
        if not settings.apify_token.strip():
            return "APIFY_TOKEN is required for --extractor apify"
        return None
    if extractor == "scrapeforge":
        if not settings.scrapeforge_key.strip():
            return "SCRAPEFORGE_KEY is required for --extractor scrapeforge"
        return None
    if extractor == "direct":
        return None
    if extractor == "chain":
        priority: list[str] = []
        if req.source == "propertyfinder":
            priority = [p.strip().lower() for p in settings.extractor_priority_propertyfinder.split(",") if p.strip()]
        elif req.source == "bayut":
            priority = [p.strip().lower() for p in settings.extractor_priority_bayut.split(",") if p.strip()]
        else:
            return None
        if "apify" in priority and not settings.apify_token.strip():
            return "APIFY_TOKEN is required for chain (apify in extractor priority)"
        if "scrapeforge" in priority and not settings.scrapeforge_key.strip():
            return "SCRAPEFORGE_KEY is required for chain (scrapeforge in extractor priority)"
        return None
    return f"unknown extractor: {extractor}"


async def _extract(extractor: str, req: LookupRequest) -> ListingPayload:
    if extractor == "chain":
        return await ExtractorChain().extract(req)
    cls = EXTRACTOR_REGISTRY.get(extractor)
    if cls is None:
        raise ExtractionError(
            code="unknown_extractor",
            message=f"unsupported extractor {extractor!r}",
            extractor=extractor,
            source=req.source,
        )
    payload = await cls().fetch(req)
    if req.source in ("propertyfinder", "bayut"):
        payload = await enrich_owner_from_dld(payload)
    return payload


def _print_payload(payload: ListingPayload, elapsed_ms: float, req: LookupRequest, raw_input: str) -> None:
    print(f"input: {raw_input}")
    print(f"detected source: {req.source}")
    print(f"external_id: {req.external_id}")
    print(f"elapsed_ms: {elapsed_ms:.1f}")
    print("")
    for key in PAYLOAD_FIELDS:
        print(f"{key}: {getattr(payload, key)}")
    print("")
    for line in format_checklist(payload):
        print(line)
    critical = format_critical_owner_line(payload)
    if critical:
        print(critical)


def _handle_raw_payload(payload: ListingPayload, raw_out: Path | None) -> None:
    raw = payload.raw_payload or {}
    if raw_out is not None:
        raw_out.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"raw_payload written: {raw_out}")
        return
    text = json.dumps(raw, indent=2, ensure_ascii=False, default=str)
    if len(text) > 3000:
        text = text[:3000] + "\n... [truncated]"
    print("raw_payload:")
    print(text)


async def _run(args: argparse.Namespace) -> int:
    configure_logging(get_settings().log_level)

    try:
        req = parse_lookup_input(args.input)
    except InputParseError as exc:
        print(f"parse error: {exc}", file=sys.stderr)
        return 1

    print(_req_line(req))
    print(f"extractor: {args.extractor}")
    print("")

    token_err = _validate_extractor_tokens(args.extractor, req)
    if token_err:
        print(token_err, file=sys.stderr)
        return 3

    started = time.perf_counter()
    try:
        payload = await _extract(args.extractor, req)
    except ExtractionError as exc:
        print(f"extraction failed: {exc}", file=sys.stderr)
        return 2
    elapsed_ms = (time.perf_counter() - started) * 1000

    _print_payload(payload, elapsed_ms, req, args.input)
    print("")
    _handle_raw_payload(payload, args.raw_out)

    if args.save_db:
        settings = get_settings()
        async with session_scope() as session:
            repo = ListingRepository(session, cache_ttl_days=settings.cache_ttl_days)
            listing = await repo.upsert_from_payload(payload.to_upsert(req))
            print(f"saved listing id={listing.id}")

    if args.save_db:
        await dispose_engine()

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local extraction test harness")
    parser.add_argument("input", help="Property Finder / Bayut URL or Trakheesi permit")
    parser.add_argument(
        "--extractor",
        choices=("apify", "scrapeforge", "direct", "chain"),
        default="chain",
    )
    parser.add_argument("--save-db", action="store_true", help="Persist result via repository upsert")
    parser.add_argument("--no-db", action="store_true", help="Do not touch the database (default)")
    parser.add_argument("--raw-out", type=Path, help="Write full raw_payload JSON to path")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    if args.save_db and args.no_db:
        print("use either --save-db or --no-db, not both", file=sys.stderr)
        raise SystemExit(1)
    try:
        code = asyncio.run(_run(args))
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(code)


if __name__ == "__main__":
    main()