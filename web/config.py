import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BASE_DIR = Path(__file__).parent.parent
TEACHER_DIR = BASE_DIR / "teacher"
TEXTBOOK_DIR = BASE_DIR / "textbook"
WEB_DIR = Path(__file__).parent


def get_active_textbook() -> tuple[Path | None, Path | None]:
    """Return (content_path, progress_path) from the active textbook in registry.
    Falls back to building-effective-agents.md for legacy compatibility."""
    from textbook_store import get_store
    store = get_store()
    content, progress = store.get_active_paths()
    if content and progress:
        cp = BASE_DIR / content
        pp = BASE_DIR / progress
        if cp.exists():
            return cp, pp
    # Legacy fallback
    default = TEXTBOOK_DIR / "building-effective-agents.md"
    if default.exists():
        return default, None
    return None, None


_content_path, _ = get_active_textbook()
TEXTBOOK_PATH = _content_path  # kept for import-time compatibility
CONVERSATIONS_DIR = WEB_DIR / "conversations"
BACKUPS_DIR = WEB_DIR / "backups"
ACTIVE_SESSION_FILE = CONVERSATIONS_DIR / "active_session.json"

TEACHER_NAMES = ["march7", "ganyu", "keqing"]
TEACHER_DISPLAY = {"march7": "三月七", "ganyu": "甘雨", "keqing": "刻晴"}

# Claude-compatible API config (DeepSeek)
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "deepseek-v4-pro[1m]")
CONTEXT_WINDOW = 1_000_000  # deepseek-v4-pro[1m]
MAX_TOKENS_RESPONSE = 4_096
SAFETY_MARGIN = 8_192
AVAILABLE_TOKEN_BUDGET = CONTEXT_WINDOW - MAX_TOKENS_RESPONSE - SAFETY_MARGIN  # 987,712


def check_config():
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("错误：未设置 ANTHROPIC_API_KEY。请在 web/.env 中配置。")
        sys.exit(1)
