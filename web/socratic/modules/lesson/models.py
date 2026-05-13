from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class EndJobStatus:
    job_id: str
    status: str  # "processing" | "done" | "failed"
    updated_files: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class LessonSession:
    session_id: str
    teacher_name: str
    teacher_display: str
    lesson_started_at: float
    messages: list[ChatMessage] = field(default_factory=list)
    end_job: EndJobStatus | None = None
