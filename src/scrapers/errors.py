from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExtractionError(Exception):
    code: str
    message: str
    extractor: str
    source: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message} (extractor={self.extractor}, source={self.source})"