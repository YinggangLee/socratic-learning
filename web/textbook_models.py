import re
from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, Field, model_validator


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


class TextbookRecord(BaseModel):
    id: str
    name: str
    content_path: str
    source_type: str  # file_md / file_pdf / url
    source_ref: str | None = None
    original_path: str | None = None
    progress_path: str
    status: TextbookStatus = TextbookStatus.inactive
    import_status: ImportStatus = ImportStatus.pending
    import_error: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_studied_at: str | None = None

    @model_validator(mode="after")
    def active_requires_ready(self):
        if self.status == TextbookStatus.active and self.import_status != ImportStatus.ready:
            raise ValueError("active status requires import_status=ready")
        return self


class TextbookCreateRequest(BaseModel):
    name: str
    source_type: str  # file_md / file_pdf / url
    source_ref: str | None = None
    set_active: bool = False

    def _generate_id(self) -> str:
        raw = self.name.lower().strip()
        raw = re.sub(r'[^a-z0-9\s-]', '', raw)
        raw = re.sub(r'\s+', '-', raw)
        return raw.strip('-') or "untitled"


class TextbookStatusRequest(BaseModel):
    status: TextbookStatus
