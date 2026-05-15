"""FastAPI-specific Pydantic schemas (adapters layer)."""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class StartResponse(BaseModel):
    teacher_name: str
    teacher_display: str
    opening_message: str


class LessonStateResponse(BaseModel):
    status: str
    teacher_name: str | None = None
    teacher_display: str | None = None
    lesson_started_at: float | None = None
    messages: list[dict] | None = None
    next_teacher: str | None = None
    has_active_textbook: bool = True


class EndResponse(BaseModel):
    job_id: str
    status: str


class ProgressResponse(BaseModel):
    status: str
    updated_files: list[str] | None = None
    error: str | None = None


class PanelResponse(BaseModel):
    name: str
    html: str


class TextbookStatusRequest(BaseModel):
    status: str
