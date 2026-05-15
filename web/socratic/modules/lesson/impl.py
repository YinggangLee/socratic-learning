"""Lesson session management implementation."""

import json
from pathlib import Path
import time
import uuid

from .errors import NoActiveLesson
from .interface import LessonSessionRepository
from .models import ChatMessage, EndJobStatus, LessonSession


class FileBackedLessonRepository:
    def __init__(self, active_session_file: Path):
        self._file = active_session_file
        self._session: LessonSession | None = None

    def get_active(self) -> LessonSession | None:
        if self._session is not None:
            return self._session
        if self._file.exists():
            try:
                data = json.loads(self._file.read_text(encoding="utf-8"))
                self._session = LessonSession(
                    session_id=data["session_id"],
                    teacher_name=data["teacher_name"],
                    teacher_display=data["teacher_display"],
                    lesson_started_at=data["lesson_started_at"],
                    messages=[ChatMessage(**m) for m in data.get("messages", [])],
                    end_job=EndJobStatus(**data["end_job"]) if data.get("end_job") else None,
                )
                return self._session
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        return None

    def save(self, session: LessonSession) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "session_id": session.session_id,
            "teacher_name": session.teacher_name,
            "teacher_display": session.teacher_display,
            "lesson_started_at": session.lesson_started_at,
            "messages": [{"role": m.role, "content": m.content} for m in session.messages],
            "end_job": {
                "job_id": session.end_job.job_id,
                "status": session.end_job.status,
                "updated_files": session.end_job.updated_files,
                "error": session.end_job.error,
            }
            if session.end_job
            else None,
        }
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.rename(self._file)
        self._session = session

    def clear(self) -> None:
        if self._file.exists():
            self._file.unlink(missing_ok=True)
        self._session = None


class SingleSessionLessonManager:
    def __init__(self, repository: LessonSessionRepository):
        self._repo = repository
        self._panel_cache: dict[str, str] = {}

    def get_session(self) -> LessonSession | None:
        return self._repo.get_active()

    def start_new(self, teacher_name: str, teacher_display: str) -> LessonSession:
        session = LessonSession(
            session_id=uuid.uuid4().hex[:12],
            teacher_name=teacher_name,
            teacher_display=teacher_display,
            lesson_started_at=time.time(),
        )
        self._repo.save(session)
        return session

    def add_message(self, role: str, content: str) -> None:
        session = self._repo.get_active()
        if session is None:
            raise NoActiveLesson()
        session.messages.append(ChatMessage(role=role, content=content))
        self._repo.save(session)

    def start_end_job(self, job_id: str) -> None:
        session = self._repo.get_active()
        if session is None:
            raise NoActiveLesson()
        session.end_job = EndJobStatus(job_id=job_id, status="processing")
        self._repo.save(session)

    def update_end_job(self, status: str, updated_files: list[str] | None = None, error: str | None = None) -> None:
        session = self._repo.get_active()
        if session and session.end_job:
            session.end_job.status = status
            if updated_files is not None:
                session.end_job.updated_files = updated_files
            if error is not None:
                session.end_job.error = error
            self._repo.save(session)

    def get_end_job(self) -> EndJobStatus | None:
        session = self._repo.get_active()
        return session.end_job if session else None

    def has_ended(self) -> bool:
        session = self._repo.get_active()
        if session is None:
            return True
        return bool(session.end_job and session.end_job.status in ("done", "failed"))

    def close_session(self) -> None:
        self._repo.clear()
        self._panel_cache.clear()

    def get_panel_cache(self) -> dict[str, str]:
        return self._panel_cache
