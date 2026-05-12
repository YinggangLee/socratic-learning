import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BASE_DIR = Path(__file__).parent.parent
TEACHER_DIR = BASE_DIR / "teacher"
TEXTBOOK_PATH = BASE_DIR / "textbook" / "building-effective-agents.md"
WEB_DIR = Path(__file__).parent
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
