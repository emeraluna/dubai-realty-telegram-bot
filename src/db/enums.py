from enum import StrEnum


class OwnerSource(StrEnum):
    SCRAPED = "scraped"
    MANUAL = "manual"
    UNKNOWN = "unknown"


class ImportRowAction(StrEnum):
    INSERTED = "inserted"
    UPDATED = "updated"
    SKIPPED = "skipped"
    ERROR = "error"


class OwnerResolveStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"