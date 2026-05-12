from pydantic import BaseModel


class Message(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str


class StartResponse(BaseModel):
    teacher_name: str
    teacher_display: str
    opening_message: str


class LessonStateResponse(BaseModel):
    status: str  # "active" | "no_active_lesson"
    teacher_name: str | None = None
    teacher_display: str | None = None
    lesson_started_at: float | None = None
    messages: list[Message] | None = None


class EndResponse(BaseModel):
    job_id: str
    status: str  # "processing"


class EndConflictResponse(BaseModel):
    conflict: bool = True
    existing_job_id: str


class ProgressResponse(BaseModel):
    status: str  # "processing" | "done" | "failed"
    updated_files: list[str] | None = None
    error: str | None = None


class PanelResponse(BaseModel):
    name: str
    html: str


class ErrorResponse(BaseModel):
    error: str
