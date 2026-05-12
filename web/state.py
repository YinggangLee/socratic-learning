import json
import time
from pathlib import Path
from models import Message
from config import ACTIVE_SESSION_FILE


class LessonState:
    def __init__(
        self,
        session_id: str,
        teacher_name: str,
        teacher_display: str,
        lesson_started_at: float | None = None,
        messages: list[Message] | None = None,
    ):
        self.session_id = session_id
        self.teacher_name = teacher_name
        self.teacher_display = teacher_display
        self.lesson_started_at = lesson_started_at or time.time()
        self.messages: list[Message] = messages or []
        self.panel_cache: dict[str, str] = {}
        self._end_job: dict | None = None  # { job_id, status, updated_files }

    def add_message(self, role: str, content: str):
        self.messages.append(Message(role=role, content=content))
        self._persist()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "teacher_name": self.teacher_name,
            "teacher_display": self.teacher_display,
            "lesson_started_at": self.lesson_started_at,
            "messages": [m.model_dump() for m in self.messages],
        }

    def _persist(self):
        ACTIVE_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_dict()
        tmp = ACTIVE_SESSION_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.rename(ACTIVE_SESSION_FILE)

    def start_end_job(self, job_id: str):
        self._end_job = {"job_id": job_id, "status": "processing", "updated_files": []}
        self._persist()

    def update_end_job(self, status: str, updated_files: list[str] | None = None, error: str | None = None):
        if self._end_job:
            self._end_job["status"] = status
            if updated_files is not None:
                self._end_job["updated_files"] = updated_files
            if error is not None:
                self._end_job["error"] = error

    def get_end_job_status(self) -> dict | None:
        return self._end_job

    def cleanup(self):
        self.panel_cache.clear()
        if ACTIVE_SESSION_FILE.exists():
            ACTIVE_SESSION_FILE.unlink()


# Single-user, single-session
_active_session: LessonState | None = None


def get_active_session() -> LessonState | None:
    global _active_session
    if _active_session is not None:
        return _active_session
    # Try to recover from disk
    if ACTIVE_SESSION_FILE.exists():
        try:
            data = json.loads(ACTIVE_SESSION_FILE.read_text(encoding="utf-8"))
            _active_session = LessonState(
                session_id=data["session_id"],
                teacher_name=data["teacher_name"],
                teacher_display=data["teacher_display"],
                lesson_started_at=data["lesson_started_at"],
                messages=[Message(**m) for m in data.get("messages", [])],
            )
            return _active_session
        except (json.JSONDecodeError, KeyError):
            pass
    return None


def create_session(teacher_name: str, teacher_display: str) -> LessonState:
    global _active_session
    import uuid
    session_id = uuid.uuid4().hex[:12]
    _active_session = LessonState(
        session_id=session_id,
        teacher_name=teacher_name,
        teacher_display=teacher_display,
    )
    _active_session._persist()
    return _active_session


def clear_session():
    global _active_session
    if _active_session:
        _active_session.cleanup()
    _active_session = None
