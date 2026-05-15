"""Lesson application service — orchestrates start/chat/end flows."""

import logging
from pathlib import Path
import time

logger = logging.getLogger("socratic.application.lesson")


class LessonService:
    def __init__(
        self,
        lesson_manager,  # LessonManager
        prompt_builder,  # PromptBuilder
        llm_client,  # AsyncLLMClient
        teacher_repo,  # TeacherProfileRepository
        textbook_catalog,  # TextbookCatalog
        panel_service,  # PanelQueryService (for cache invalidation)
        base_dir: Path,
    ):
        self._manager = lesson_manager
        self._prompt = prompt_builder
        self._llm = llm_client
        self._teachers = teacher_repo
        self._catalog = textbook_catalog
        self._panels = panel_service
        self._base_dir = base_dir

    # ── State ──

    def get_state(self) -> dict:
        session = self._manager.get_session()
        if session is not None and self._manager.has_ended():
            session = None
        if session is None:
            # No active lesson — compute next teacher from progress
            progress_text = ""
            try:
                active = self._catalog.get_active()
                if active:
                    progress_path = self._base_dir / active.progress_path
                    if progress_path.exists():
                        progress_text = progress_path.read_text(encoding="utf-8")
            except Exception:
                pass
            next_teacher_en = self._teachers.determine_next_teacher(progress_text) if progress_text else "march7"
            next_teacher_display = self._teachers.get_teacher_display(next_teacher_en)
            return {"status": "no_active_lesson", "next_teacher": next_teacher_display}
        return {
            "status": "active",
            "teacher_name": session.teacher_name,
            "teacher_display": session.teacher_display,
            "lesson_started_at": session.lesson_started_at,
            "messages": [{"role": m.role, "content": m.content} for m in session.messages],
        }

    # ── Start ──

    async def start_lesson(self) -> dict:
        existing = self._manager.get_session()
        if existing is not None:
            if self._manager.has_ended():
                self._manager.close_session()
            else:
                return {"conflict": True}

        teacher_name, teacher_display, system_prompt = self._prompt.build_start_prompt()
        logger.info(f"开始新课，授课老师: {teacher_display}")

        try:
            response = await self._llm.create_message(
                system=system_prompt,
                messages=[{"role": "user", "content": "请开始上课。"}],
            )
        except Exception as e:
            logger.error(f"生成开场白失败: {e}")
            return {"error": f"生成开场白失败: {e}"}

        opening_message = response if response else "（老师暂时没有想好怎么开场……）"
        self._manager.start_new(teacher_name, teacher_display)
        self._manager.add_message("assistant", opening_message)

        return {
            "teacher_name": teacher_name,
            "teacher_display": teacher_display,
            "opening_message": opening_message,
        }

    # ── Chat ──

    async def chat(self, message: str) -> dict:
        session = self._manager.get_session()
        if session is None:
            return {"error": "没有活跃课程，请先开始上课"}

        self._manager.add_message("user", message)

        elapsed = time.time() - session.lesson_started_at
        remaining = max(0, 50 * 60 - elapsed)
        remaining_minutes = int(remaining / 60) if remaining < 600 else None

        messages = [{"role": m.role, "content": m.content} for m in session.messages]
        system_prompt, api_messages = self._prompt.build_chat_messages(
            teacher_name=session.teacher_name,
            messages=messages,
            remaining_minutes=remaining_minutes,
        )

        return {
            "system_prompt": system_prompt,
            "api_messages": api_messages,
            "teacher_name": session.teacher_name,
        }

    def get_stream(self, system_prompt: str, api_messages: list[dict]):
        """Return an async iterator of SSE event dicts."""
        return self._llm.stream_message(system=system_prompt, messages=api_messages)

    def finalize_chat_message(self, full_text: str):
        self._manager.add_message("assistant", full_text)

    # ── End ──

    def end_lesson(self, job_id: str) -> dict:
        session = self._manager.get_session()
        if session is None:
            return {"error": "没有活跃课程"}
        if self._manager.get_end_job() is not None and self._manager.get_end_job().status == "processing":
            return {"conflict": True, "existing_job_id": self._manager.get_end_job().job_id}
        self._manager.start_end_job(job_id)
        return {"job_id": job_id, "status": "processing"}

    def get_end_progress(self, job_id: str) -> dict:
        session = self._manager.get_session()
        if session is None:
            return {"status": "failed", "error": "没有活跃课程"}
        job = self._manager.get_end_job()
        if job is None:
            return {"status": "failed", "error": "未找到该任务"}
        return {"status": job.status, "updated_files": job.updated_files, "error": job.error}

    # ── Clear ──

    def clear(self):
        self._manager.close_session()
