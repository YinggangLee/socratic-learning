from pathlib import Path

from socratic.application.textbook_service import TextbookService
from socratic.modules.lesson.impl import FileBackedLessonRepository, SingleSessionLessonManager
from socratic.modules.textbook.impl import JsonTextbookCatalog


class NoopJobRunner:
    def run_background(self, fn, *args, **kwargs) -> None:
        pass


class DummyLLMClient:
    async def create_message(self, system: str, messages: list[dict], max_tokens: int = 4096) -> str:
        return ""


class DummyStorage:
    pass


def test_server_app_imports(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    import server

    assert server.app.title == "苏格拉底·七 Web 家教系统"


def test_lesson_clear_removes_cached_session(tmp_path: Path):
    repo = FileBackedLessonRepository(tmp_path / "active_session.json")
    manager = SingleSessionLessonManager(repo)

    manager.start_new("march7", "三月七")
    assert manager.get_session() is not None

    manager.close_session()
    assert manager.get_session() is None


def test_create_markdown_textbook_with_set_active_activates_after_import(tmp_path: Path):
    catalog = JsonTextbookCatalog(tmp_path / "textbook" / "registry.json", tmp_path)
    service = TextbookService(catalog, DummyLLMClient(), NoopJobRunner(), DummyStorage(), tmp_path)

    created = service.create_textbook("My Book", "file_md", set_active=True)
    imported = service.import_file_md(created["id"], b"# Chapter\n\nContent", "book.md")

    assert imported["status"] == "active"
    assert service.list_textbooks()["active_id"] == created["id"]
