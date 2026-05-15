"""Composition Root — the only file allowed to import impl.py modules."""

import os
from pathlib import Path
import sys

from .config import AppSettings


class AppContainer:
    def __init__(self, settings: AppSettings | None = None):
        self._settings = settings or AppSettings()
        self._services_initialized = False

    def init_services(self):
        """Wire all implementations together. Called once at startup."""
        if self._services_initialized:
            return

        s = self._settings

        # ── Infrastructure ──
        from socratic.infrastructure.jobs.impl import AsyncioJobRunner
        from socratic.infrastructure.llm.impl import AnthropicLLMClient
        from socratic.infrastructure.storage.impl import LocalFileStorage

        self.llm_client = AnthropicLLMClient(
            base_url=s.llm_base_url,
            model=s.llm_model,
            api_key=s.llm_api_key or os.getenv("ANTHROPIC_API_KEY", ""),
            max_tokens=s.max_tokens_response,
        )
        self.storage = LocalFileStorage()
        self.job_runner = AsyncioJobRunner()

        # ── Teacher Profiles ──
        from socratic.modules.teacher_profile.impl import MarkdownTeacherProfileRepository

        self.teacher_repo = MarkdownTeacherProfileRepository(
            teacher_dir=s.teacher_dir,
            teacher_names=s.teacher_names,
            teacher_display=s.teacher_display,
        )

        # ── Textbook Catalog ──
        from socratic.modules.textbook.impl import JsonTextbookCatalog

        catalog_path = s.textbook_registry_path
        if not catalog_path.exists():
            md_path = s.textbook_dir / "textbook_registry.md"
            if md_path.exists():
                from socratic.modules.textbook.migrate_registry import migrate_from_legacy

                migrate_from_legacy(s.textbook_dir, catalog_path)
        self.textbook_catalog = JsonTextbookCatalog(catalog_path, s.base_dir)

        # ── Prompt Builder ──
        from socratic.modules.prompt.impl import TokenBudgetPromptBuilder

        self.prompt_builder = TokenBudgetPromptBuilder(
            teacher_repo=self.teacher_repo,
            textbook_catalog=self.textbook_catalog,
            storage=self.storage,
            teacher_dir=s.teacher_dir,
            teacher_names=s.teacher_names,
            teacher_display=s.teacher_display,
        )

        # ── Panel Service (needs lazy progress/textbook callbacks) ──
        from socratic.modules.panels.impl import CachedPanelService, MarkdownPanelRenderer

        def _get_progress_text() -> str:
            try:
                # Re-use existing prompt builder info
                return ""
            except Exception:
                return ""

        def _get_active_textbook_path() -> Path:
            try:
                active = self.textbook_catalog.get_active()
                if active:
                    return s.base_dir / active.content_path
            except Exception:
                pass
            legacy = s.textbook_dir / "building-effective-agents.md"
            if legacy.exists():
                return legacy
            return s.textbook_dir / "nonexistent.md"

        renderer = MarkdownPanelRenderer()
        self.panel_query_service = CachedPanelService(
            renderer=renderer,
            teacher_repo=self.teacher_repo,
            textbook_catalog=self.textbook_catalog,
            storage=self.storage,
            teacher_dir=s.teacher_dir,
            teacher_names=s.teacher_names,
            teacher_display=s.teacher_display,
            get_progress_text=self._get_progress_text,
            get_active_textbook_path=_get_active_textbook_path,
        )

        # ── Lesson Manager ──
        from socratic.modules.lesson.impl import FileBackedLessonRepository, SingleSessionLessonManager

        lesson_repo = FileBackedLessonRepository(s.active_session_file)
        self.lesson_manager = SingleSessionLessonManager(lesson_repo)

        # ── Application Services ──
        from socratic.application.lesson_service import LessonService
        from socratic.application.panel_service import PanelService
        from socratic.application.post_lesson_service import PostLessonService
        from socratic.application.textbook_service import TextbookService

        self.lesson_service = LessonService(
            lesson_manager=self.lesson_manager,
            prompt_builder=self.prompt_builder,
            llm_client=self.llm_client,
            teacher_repo=self.teacher_repo,
            textbook_catalog=self.textbook_catalog,
            panel_service=self.panel_query_service,
            base_dir=s.base_dir,
        )
        self.textbook_service = TextbookService(
            catalog=self.textbook_catalog,
            llm_client=self.llm_client,
            job_runner=self.job_runner,
            storage=self.storage,
            base_dir=s.base_dir,
        )
        self.post_lesson_service = PostLessonService(
            lesson_manager=self.lesson_manager,
            textbook_catalog=self.textbook_catalog,
            llm_client=self.llm_client,
            teacher_dir=s.teacher_dir,
            backups_dir=s.base_dir / "web" / "backups",
            base_dir=s.base_dir,
        )
        self.panel_service = PanelService(panel_query_service=self.panel_query_service)

        self._services_initialized = True

    def _get_progress_text(self) -> str:
        """Resolve progress text dynamically on each call."""
        try:
            active = self.textbook_catalog.get_active()
            if active:
                progress_path = self._settings.base_dir / active.progress_path
                if progress_path.exists():
                    return progress_path.read_text(encoding="utf-8")
        except Exception:
            pass
        progress_dir = self._settings.teacher_dir / "progress"
        if progress_dir.exists():
            for f in sorted(progress_dir.iterdir()):
                if f.suffix == ".md":
                    return f.read_text(encoding="utf-8")
        return ""

    def check_config(self):
        if not (self._settings.llm_api_key or os.getenv("ANTHROPIC_API_KEY")):
            print("错误：未设置 ANTHROPIC_API_KEY。请在 web/.env 中配置。")
            sys.exit(1)
