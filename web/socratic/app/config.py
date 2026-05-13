"""Settings dataclass — no business logic, no file I/O at import time."""
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppSettings:
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent.parent.parent)
    llm_base_url: str = "https://api.deepseek.com/anthropic"
    llm_model: str = "deepseek-v4-pro[1m]"
    llm_api_key: str = ""
    max_tokens_response: int = 4096
    context_window: int = 1_000_000
    safety_margin: int = 8192
    teacher_names: list[str] = field(default_factory=lambda: ["march7", "ganyu", "keqing"])
    teacher_display: dict = field(default_factory=lambda: {"march7": "三月七", "ganyu": "甘雨", "keqing": "刻晴"})

    @property
    def teacher_dir(self) -> Path:
        return self.base_dir / "teacher"

    @property
    def textbook_dir(self) -> Path:
        return self.base_dir / "textbook"

    @property
    def textbook_registry_path(self) -> Path:
        return self.textbook_dir / "registry.json"

    @property
    def active_session_file(self) -> Path:
        return self.base_dir / "web" / "conversations" / "active_session.json"
