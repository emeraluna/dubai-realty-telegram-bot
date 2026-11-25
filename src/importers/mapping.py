from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz

from config import get_settings

CANONICAL_FIELDS = [
    "permit_number",
    "source_listing_id",
    "source_url",
    "unit_number",
    "floor",
    "building",
    "community",
    "developer",
    "size_sqft",
    "plot_number",
    "owner_name",
    "owner_phone",
]

ALIASES: dict[str, tuple[str, ...]] = {
    "permit_number": ("permit", "trakheesi", "trakheesi no", "permit no", "permit_number"),
    "source_listing_id": ("listing id", "listing_id", "id"),
    "source_url": ("url", "link", "listing url", "source_url"),
    "unit_number": ("unit", "unit no", "unit_number"),
    "floor": ("floor",),
    "building": ("building", "tower", "building name"),
    "community": ("community", "area", "location"),
    "developer": ("developer", "developer name"),
    "size_sqft": ("size", "size sqft", "area sqft", "size_sqft"),
    "plot_number": ("plot", "plot no", "plot_number"),
    "owner_name": ("owner", "owner name", "landlord", "owner_name"),
    "owner_phone": ("phone", "mobile", "contact", "contact number", "owner_phone"),
}


def _norm(header: str) -> str:
    return re.sub(r"\s+", " ", header.strip().lower())


def map_headers(
    headers: list[str],
    *,
    override: dict[str, str] | None = None,
) -> tuple[dict[str, str], list[str]]:
    settings = get_settings()
    threshold = settings.import_fuzzy_threshold
    column_map: dict[str, str] = {}
    warnings: list[str] = []
    scores: dict[str, float] = {}

    normalized_headers = {h: _norm(h) for h in headers}
    if override:
        for header, target in override.items():
            if header in headers and target in CANONICAL_FIELDS:
                column_map[header] = target
                scores[target] = 100.0

    for header, norm in normalized_headers.items():
        if header in column_map:
            continue
        for target, aliases in ALIASES.items():
            if norm == target or norm in aliases:
                existing_header = next((h for h, t in column_map.items() if t == target), None)
                if existing_header and existing_header != header:
                    warnings.append(
                        f"alias collision on '{target}' between '{existing_header}' and '{header}'"
                    )
                column_map[header] = target
                scores[target] = 100.0
                break

    for header, norm in normalized_headers.items():
        if header in column_map:
            continue
        best_target = None
        best_score = 0.0
        for target in CANONICAL_FIELDS:
            candidates = (target, *ALIASES.get(target, ()))
            for cand in candidates:
                score = float(fuzz.ratio(norm, cand))
                if score > best_score:
                    best_score = score
                    best_target = target
        if best_target and best_score >= threshold:
            prev = scores.get(best_target, -1)
            if best_score > prev:
                if prev >= 0:
                    warnings.append(
                        f"fuzzy collision on '{best_target}': replaced prior mapping (score {prev:.0f} -> {best_score:.0f})"
                    )
                    for h, t in list(column_map.items()):
                        if t == best_target and h != header:
                            del column_map[h]
                column_map[header] = best_target
                scores[best_target] = best_score

    return column_map, warnings


def row_to_fields(row: dict[str, Any], column_map: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for header, value in row.items():
        target = column_map.get(header)
        if not target:
            continue
        if value is None:
            continue
        if isinstance(value, float) and value != value:
            continue
        text = str(value).strip()
        if not text:
            continue
        if target == "size_sqft":
            try:
                out[target] = float(text.replace(",", ""))
            except ValueError:
                out[target] = text
        else:
            out[target] = text
    return out