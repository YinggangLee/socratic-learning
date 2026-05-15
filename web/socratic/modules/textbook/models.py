from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class TextbookStatus(StrEnum):
    active = "active"
    inactive = "inactive"
    completed = "completed"
    deleted = "deleted"


class ImportStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


@dataclass
class TextbookRecord:
    id: str
    name: str
    content_path: str
    source_type: str
    progress_path: str
    source_ref: str | None = None
    original_path: str | None = None
    status: TextbookStatus = TextbookStatus.inactive
    import_status: ImportStatus = ImportStatus.pending
    import_error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_studied_at: str | None = None


@dataclass
class CreateTextbookCommand:
    name: str
    source_type: str
    source_ref: str | None = None
    set_active: bool = False
