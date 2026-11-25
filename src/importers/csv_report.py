from __future__ import annotations

import csv
import io
import json
from typing import Iterable

from db.models import ImportRow


def build_error_report_csv(rows: Iterable[ImportRow]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["row_index", "error", "raw_row"])
    for row in rows:
        writer.writerow([row.row_index, row.error or "", json.dumps(row.raw_row, ensure_ascii=False)])
    return buffer.getvalue().encode("utf-8-sig")