"""Application settings loaded once in the composition root."""

from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv


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

    @classmethod
    def from_env(cls, base_dir: Path | None = None) -> "AppSettings":
        resolved_base = base_dir or Path(__file__).parent.parent.parent.parent
        load_dotenv(resolved_base / "web" / ".env", override=False)
        load_dotenv(resolved_base / ".env", override=False)
        return cls(
            base_dir=resolved_base,
            llm_base_url=os.getenv("ANTHROPIC_BASE_URL", cls.llm_base_url),
            llm_model=os.getenv("ANTHROPIC_MODEL", cls.llm_model),
            llm_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            max_tokens_response=_env_int("MAX_TOKENS_RESPONSE", cls.max_tokens_response),
            context_window=_env_int("CONTEXT_WINDOW", cls.context_window),
            safety_margin=_env_int("SAFETY_MARGIN", cls.safety_margin),
        )


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default
