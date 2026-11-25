from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import httpx

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config import get_settings  # noqa: E402

CONTACT_KEY_RE = re.compile(
    r"(phone|mobile|contact|owner|landlord|whatsapp|tel)",
    re.IGNORECASE,
)
ITEM_TRUNC = 4000


def _collect_keys(obj: Any, prefix: str = "") -> list[str]:
    keys: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            keys.append(path)
            keys.extend(_collect_keys(value, path))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            keys.extend(_collect_keys(value, f"{prefix}[{index}]"))
    return keys


def _contact_like_keys(keys: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for key in keys:
        leaf = key.split(".")[-1].split("[")[0]
        if CONTACT_KEY_RE.search(leaf) and key not in seen:
            seen.add(key)
            out.append(key)
    return sorted(out)


def _load_body(url: str, input_json: Path | None) -> dict[str, Any]:
    if input_json is not None:
        data = json.loads(input_json.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("--input-json must contain a JSON object")
        return data
    return {"startUrls": [{"url": url}]}


def _run(url: str, actor: str, input_json: Path | None) -> int:
    settings = get_settings()
    token = settings.apify_token.strip()
    if not token:
        print("APIFY_TOKEN is missing", file=sys.stderr)
        return 1

    body = _load_body(url, input_json)
    endpoint = f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
    with httpx.Client(timeout=httpx.Timeout(300.0)) as client:
        response = client.post(
            endpoint,
            params={"token": token, "format": "json"},
            json=body,
        )
    if response.status_code >= 400:
        print(f"Apify HTTP {response.status_code}: {response.text[:2000]}", file=sys.stderr)
        return 1

    data = response.json()
    if not isinstance(data, list):
        print("Unexpected response: expected a JSON array", file=sys.stderr)
        return 1

    print(f"dataset items: {len(data)}")
    all_contact_keys: set[str] = set()

    for index, item in enumerate(data, start=1):
        print(f"\n--- item {index} keys ---")
        if not isinstance(item, dict):
            print(type(item))
            continue
        print(", ".join(sorted(item.keys())))
        contact = _contact_like_keys(_collect_keys(item))
        all_contact_keys.update(contact)
        blob = json.dumps(item, indent=2, ensure_ascii=False, default=str)
        if len(blob) > ITEM_TRUNC:
            blob = blob[:ITEM_TRUNC] + "\n... [truncated]"
        print(blob)

    print("\n--- contact summary ---")
    print(f"Detected contact-like keys: {sorted(all_contact_keys)}")
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Raw Apify Actor dataset probe")
    parser.add_argument("url", help="Listing URL to pass to the Actor")
    parser.add_argument("--actor", required=True, help="Apify Actor ID")
    parser.add_argument("--input-json", type=Path, help="Optional Actor input JSON file")
    args = parser.parse_args(argv)
    raise SystemExit(_run(args.url, args.actor, args.input_json))


if __name__ == "__main__":
    main()