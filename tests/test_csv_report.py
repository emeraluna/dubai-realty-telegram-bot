from __future__ import annotations

import csv
import json
from io import StringIO

from db.enums import ImportRowAction
from db.models import ImportRow
from importers.csv_report import build_error_report_csv


def test_build_error_report_csv_columns_and_encoding() -> None:
    rows = [
        ImportRow(
            id=1,
            batch_id=9,
            row_index=2,
            action=ImportRowAction.ERROR.value,
            matched_listing_id=None,
            error="forced row failure",
            raw_row={"permit": "7555666777888", "owner name": "Bad"},
        )
    ]
    data = build_error_report_csv(rows)
    text = data.decode("utf-8-sig")
    reader = csv.reader(StringIO(text))
    header = next(reader)
    assert header == ["row_index", "error", "raw_row"]
    row_index, error, raw_json = next(reader)
    assert row_index == "2"
    assert error == "forced row failure"
    assert json.loads(raw_json)["permit"] == "7555666777888"