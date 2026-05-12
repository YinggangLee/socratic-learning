import json
import shutil
import re
import logging
from pathlib import Path
from datetime import datetime

from config import (
    TEACHER_DIR, BACKUPS_DIR, MAX_TOKENS_RESPONSE,
    ANTHROPIC_MODEL, ANTHROPIC_BASE_URL,
)
from error_handler import api_call_with_retry, safe_parse_json

logger = logging.getLogger("socratic_web.post_lesson")

# The 6 files updated after each lesson, with validation rules
POST_LESSON_FILES = [
    {
        "key": "progress",
        "path": None,  # Set dynamically based on active textbook
        "description": "学习进度（学到哪一章哪一节、掌握情况）",
        "validate": lambda text: text and len(text) > 50 and "##" in text,
    },
    {
        "key": "session_archive",
        "path": TEACHER_DIR / "session_archive.md",
        "description": "陈旧进度记录归档追加",
        "validate": lambda text: text is not None and len(text) >= 0,
    },
    {
        "key": "book_revision_notes",
        "path": TEACHER_DIR / "book_revision_notes.md",
        "description": "本节课暴露的教材改进点",
        "validate": lambda text: text is not None,
    },
    {
        "key": "diary",
        "path": TEACHER_DIR / "diary.md",
        "description": "学习日记——以我视角的生活化记录",
        "validate": lambda text: text and len(text) > 100 and ("#" in text),
    },
    {
        "key": "wechat_unread",
        "path": TEACHER_DIR / "wechat_unread.md",
        "description": "三位女生围绕课堂的群聊闲聊",
        "validate": lambda text: text and len(text) > 50 and "**" in text,
    },
    {
        "key": "teacher_persona",
        "path": None,  # Set dynamically based on teacher
        "description": "授课教师的情感态度变化更新",
        "validate": lambda text: text and len(text) > 100 and ("#" in text),
    },
]

MAX_BACKUPS = 10


async def run_post_lesson_pipeline(
    session,
    anthropic_client,
    progress_file: Path,
    teacher_name: str,
    teacher_display: str,
) -> dict:
    """Execute the full post-lesson update pipeline. Returns { success, updated_files, error }."""

    # Read current file contents for context
    current_files = {}
    for fdef in POST_LESSON_FILES:
        if fdef["key"] == "progress":
            fdef["path"] = progress_file
        elif fdef["key"] == "teacher_persona":
            fdef["path"] = TEACHER_DIR / f"{teacher_name}.md"
        path = fdef["path"]
        if path and path.exists():
            current_files[fdef["key"]] = path.read_text(encoding="utf-8")

    # Build the update prompt
    messages = [m.model_dump() for m in session.messages]
    conversation_text = _format_conversation(messages)
    progress_text = current_files.get("progress", "")
    diary_text = current_files.get("diary", "")
    wechat_text = current_files.get("wechat_unread", "")
    persona_text = current_files.get("teacher_persona", "")

    prompt = _build_update_prompt(
        teacher_display=teacher_display,
        conversation_text=conversation_text,
        progress_text=progress_text,
        diary_text=diary_text,
        wechat_text=wechat_text,
        persona_text=persona_text,
    )

    # Call Claude to generate updates (with retry)
    updates = None
    for attempt in range(3):
        try:
            response = await api_call_with_retry(
                anthropic_client.messages.create,
                model=ANTHROPIC_MODEL,
                max_tokens=MAX_TOKENS_RESPONSE * 2,
                messages=[{"role": "user", "content": prompt}],
                thinking={"type": "disabled"},
            )
            # Collect text from all text blocks (skip thinking blocks)
            text_parts = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif hasattr(block, 'text'):
                    text_parts.append(block.text)
            text = "".join(text_parts)
            if not text:
                logger.warning(f"API 返回空文本 (attempt {attempt + 1}), content types: {[b.type for b in response.content]}")
                continue
            updates = safe_parse_json(text, f"课后更新 (attempt {attempt + 1})")
            if updates and all(k in updates for k in ["progress", "diary", "wechat_unread"]):
                break
            logger.warning(f"JSON 解析后缺少必要字段 (attempt {attempt + 1}), keys: {list(updates.keys()) if updates else 'None'}")
            updates = None
        except Exception as e:
            logger.error(f"课后更新 API 调用失败 (attempt {attempt + 1}): {e}")
            if attempt == 2:
                return {"success": False, "updated_files": [], "error": str(e)}

    if updates is None:
        return {"success": False, "updated_files": [], "error": "无法解析 Claude 返回的更新内容"}

    # Backup current files
    backup_dir = BACKUPS_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backed_up = []

    for fdef in POST_LESSON_FILES:
        path = fdef["path"]
        if path and path.exists():
            backup_path = backup_dir / path.name
            shutil.copy2(path, backup_path)
            backed_up.append((path, backup_path))

    # Write and validate each file
    updated = []
    for fdef in POST_LESSON_FILES:
        key = fdef["key"]
        path = fdef["path"]
        new_content = updates.get(key)
        if new_content is None or path is None:
            continue

        try:
            path.write_text(new_content, encoding="utf-8")
            if fdef["validate"](new_content):
                updated.append(key)
                logger.info(f"✓ 已更新 {path.name}")
            else:
                raise ValueError(f"验证失败: {key}")
        except Exception as e:
            logger.error(f"✗ 更新 {path.name} 失败: {e}")
            # Rollback all previously written files
            _rollback(backed_up)
            shutil.rmtree(backup_dir, ignore_errors=True)
            return {"success": False, "updated_files": updated, "error": str(e)}

    # Clean old backups
    _cleanup_backups()

    logger.info(f"课后更新完成，已更新 {len(updated)} 个文件")
    return {"success": True, "updated_files": updated, "error": None}


def _format_conversation(messages: list[dict]) -> str:
    parts = []
    for m in messages[-30:]:
        role = "学生" if m["role"] == "user" else "老师"
        content = m["content"][:500]
        parts.append(f"**{role}**: {content}")
    return "\n\n".join(parts)


def _build_update_prompt(teacher_display, conversation_text, progress_text, diary_text, wechat_text, persona_text) -> str:
    return f"""你是苏格拉底·七家教系统的课后更新助手。刚刚结束了一节课，授课老师是{teacher_display}。

请根据以下对话内容，生成 6 个文件的更新内容。以 JSON 格式返回，每个字段包含文件的新完整内容。

## 对话记录
{conversation_text}

## 当前文件内容

### progress.md
{progress_text[:2000]}

### diary.md
{diary_text[:3000]}

### wechat_unread.md
{wechat_text[:2000]}

### 授课老师人设
{persona_text[:1000]}

## 输出格式

返回一个 JSON 对象，包含以下字段：

```json
{{
  "progress": "完整的 progress.md 新内容...",
  "session_archive": "归档追加的内容...",
  "book_revision_notes": "教材改进点...",
  "diary": "完整的 diary.md 新内容...",
  "wechat_unread": "完整的 wechat_unread.md 新内容...",
  "teacher_persona": "完整的教师人设新内容..."
}}
```

**更新规则：**
1. progress: 更新学习进度表，新增本节课记录，更新"当前章节"和"下一位授课老师"
2. session_archive: 将陈旧进度记录转移归档，追加到现有内容后面
3. book_revision_notes: 如果本节课暴露了教材的改进点则记录
4. diary: 以"我"（港子）的视角写一篇生活化日记，细腻情感，300-500字
5. wechat_unread: 三位女生围绕课堂内容在微信群闲聊，符合各人设，使用 **角色名：消息** 格式
6. teacher_persona: 更新授课老师"与我的关系"部分中的"当前的内心态度"

只返回 JSON，不要其他内容。"""


def _rollback(backed_up: list):
    for original_path, backup_path in backed_up:
        try:
            shutil.copy2(backup_path, original_path)
            logger.info(f"已回滚 {original_path.name}")
        except Exception as e:
            logger.error(f"回滚 {original_path.name} 失败: {e}")


def _cleanup_backups():
    backups = sorted(BACKUPS_DIR.iterdir(), key=lambda p: p.name, reverse=True)
    for old in backups[MAX_BACKUPS:]:
        if old.is_dir():
            shutil.rmtree(old)
            logger.info(f"已清理旧备份 {old.name}")
