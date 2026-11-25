from __future__ import annotations

import json
import re
from typing import Any

_SCRIPT_JSON = re.compile(
    r"<script[^>]*>(?P<body>.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_ASSIGN_JSON = re.compile(
    r"(?:window\.)?(?:__NUXT__|__INITIAL_STATE__|__PRELOADED_STATE__)\s*=\s*(?P<body>\{[\s\S]*?\});",
    re.IGNORECASE,
)


def _walk(obj: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        found.append(obj)
        for value in obj.values():
            found.extend(_walk(value))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_walk(item))
    return found


def extract_embedded_nodes(html: str) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []

    for match in _ASSIGN_JSON.finditer(html):
        body = match.group("body").strip()
        try:
            nodes.extend(_walk(json.loads(body)))
        except json.JSONDecodeError:
            continue

    for match in _SCRIPT_JSON.finditer(html):
        body = match.group("body").strip()
        if not body or "{" not in body:
            continue
        if "application/ld+json" in match.group(0).lower():
            continue
        if "__NEXT_DATA__" in match.group(0):
            continue
        if not body.startswith("{") and not body.startswith("["):
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            continue
        nodes.extend(_walk(data))

    return nodes