from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from scrapers.payload import ListingPayload

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "test_extract.py"


@pytest.fixture(scope="module")
def test_extract_module():
    spec = importlib.util.spec_from_file_location("test_extract_harness", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_checklist_all_pass(test_extract_module) -> None:
    payload = ListingPayload(
        owner_name="Owner",
        owner_phone="+971500000000",
        permit_number="7111111111111",
        building="Tower A",
    )
    lines = test_extract_module.format_checklist(payload)
    assert lines == [
        "[PASS] owner_name",
        "[PASS] owner_phone",
        "[PASS] permit_number",
        "[PASS] building",
    ]
    assert test_extract_module.format_critical_owner_line(payload) is None


def test_checklist_owner_miss_and_critical(test_extract_module) -> None:
    payload = ListingPayload(
        owner_name=None,
        owner_phone=None,
        permit_number="7111111111111",
        building="Tower A",
    )
    lines = test_extract_module.format_checklist(payload)
    assert "[MISS] owner_name" in lines
    assert "[MISS] owner_phone" in lines
    assert test_extract_module.format_critical_owner_line(payload) == "MISSING CRITICAL: owner_contact"