"""Post-lesson update pipeline."""

from __future__ import annotations

import contextlib
from datetime import datetime
import json
import logging
from pathlib import Path
import re
import shutil
from typing import Any

logger = logging.getLogger("socratic.application.post_lesson")

APPEND_KEYS = {"session_archive", "book_revision_notes"}


class PostLessonService:
    def __init__(
        self, lesson_manager, textbook_catalog, llm_client, teacher_dir: Path, backups_dir: Path, base_dir: Path
    ):
        self._lesson_manager = lesson_manager
        self._catalog = textbook_catalog
        self._llm = llm_client
        self._teacher_dir = teacher_dir
        self._backups_dir = backups_dir
        self._base_dir = base_dir

    async def run(self, job_id: str) -> None:
        session = self._lesson_manager.get_session()
        if session is None:
            self._lesson_manager.update_end_job("failed", error="没有活跃课程")
            return

        files_def = self._build_file_defs(session.teacher_name)
        self._resolve_progress_path(files_def)
        current_files = self._read_current_files(files_def)
        prompt = self._build_update_prompt(session, current_files)
        updates, error = await self._generate_updates(prompt)
        if updates is None:
            self._lesson_manager.update_end_job("failed", error=error or "无法解析 Claude 返回的更新内容")
            return

        backup_dir, backed_up = self._backup_files(files_def)
        updated = self._write_updates(files_def, updates, backed_up, backup_dir)
        if updated is None:
            return

        self._cleanup_backups()
        self._lesson_manager.update_end_job("done", updated_files=updated)
        logger.info("课后更新完成，已更新 %s 个文件", len(updated))

    def _build_file_defs(self, teacher_name: str) -> list[dict[str, Any]]:
        return [
            {"key": "progress", "path": None, "validate": lambda t: t and len(t) > 50 and "##" in t},
            {
                "key": "session_archive",
                "path": self._teacher_dir / "session_archive.md",
                "validate": lambda t: t is not None,
            },
            {
                "key": "book_revision_notes",
                "path": self._teacher_dir / "book_revision_notes.md",
                "validate": lambda t: t is not None,
            },
            {
                "key": "diary",
                "path": self._teacher_dir / "diary.md",
                "validate": lambda t: t and len(t) > 100 and "#" in t,
            },
            {
                "key": "wechat_unread",
                "path": self._teacher_dir / "wechat_unread.md",
                "validate": lambda t: t and len(t) > 50 and "**" in t,
            },
            {
                "key": "teacher_persona",
                "path": self._teacher_dir / f"{teacher_name}.md",
                "validate": lambda t: t and len(t) > 100 and "#" in t,
            },
        ]

    def _resolve_progress_path(self, files_def: list[dict[str, Any]]) -> None:
        try:
            active = self._catalog.get_active()
            if active:
                files_def[0]["path"] = self._base_dir / active.progress_path
                return
            progress_dir = self._teacher_dir / "progress"
            for progress_file in sorted(progress_dir.iterdir()) if progress_dir.exists() else []:
                if progress_file.suffix == ".md":
                    files_def[0]["path"] = progress_file
                    return
        except Exception as exc:
            logger.warning("解析进度文件失败: %s", exc)

    def _read_current_files(self, files_def: list[dict[str, Any]]) -> dict[str, str]:
        current_files = {}
        for file_def in files_def:
            path = file_def["path"]
            if path and path.exists():
                current_files[file_def["key"]] = path.read_text(encoding="utf-8")
        return current_files

    def _build_update_prompt(self, session, current_files: dict[str, str]) -> str:
        conv_parts = []
        for message in session.messages[-30:]:
            role = "学生" if message.role == "user" else "老师"
            conv_parts.append(f"**{role}**: {message.content[:500]}")
        conv_text = "\n\n".join(conv_parts)

        return f"""你是苏格拉底·七家教系统的课后更新助手。刚刚结束了一节课，授课老师是{session.teacher_display}。

请根据以下对话内容，生成 6 个文件的更新内容。以 JSON 格式返回，每个字段包含文件的新完整内容（session_archive 和 book_revision_notes 只返回本节需要追加的新内容，不包含历史）。

## 对话记录
{conv_text}

## 当前文件内容

### progress.md
{current_files.get("progress", "")[:2000]}

### diary.md
{current_files.get("diary", "")[:3000]}

### wechat_unread.md
{current_files.get("wechat_unread", "")[:2000]}

### 授课老师人设
{current_files.get("teacher_persona", "")[:1000]}

### session_archive.md（已有历史内容，仅返回本节追加部分）
{current_files.get("session_archive", "")[:500]}

### book_revision_notes.md（已有历史内容，仅返回本节追加部分）
{current_files.get("book_revision_notes", "")[:500]}

## 输出格式

返回一个 JSON 对象，包含以下字段：

```json
{{
  "progress": "完整的 progress.md 新内容...",
  "session_archive": "仅本节需要追加的归档内容...",
  "book_revision_notes": "仅本节新发现的教材改进点...",
  "diary": "完整的 diary.md 新内容...",
  "wechat_unread": "完整的 wechat_unread.md 新内容...",
  "teacher_persona": "完整的教师人设新内容..."
}}
```

**更新规则：**
1. progress: 更新学习进度表，新增本节课记录，更新"当前章节"和"下一位授课老师"
2. session_archive: 仅返回本节课需要追加的归档条目（系统会自动追加到文件末尾）
3. book_revision_notes: 仅返回本节课新发现的教材改进点（系统会自动追加到文件末尾），无新发现则返回空字符串
4. diary: 以"我"（港子）的视角写一篇生活化日记，细腻情感，300-500字
5. wechat_unread: 三位女生围绕课堂内容在微信群闲聊，符合各人设，使用 **角色名：消息** 格式
6. teacher_persona: 更新授课老师"与我的关系"部分中的"当前的内心态度"

只返回 JSON，不要其他内容。"""

    async def _generate_updates(self, prompt: str) -> tuple[dict[str, str] | None, str | None]:
        last_error = None
        for attempt in range(3):
            try:
                response = await self._llm.create_message(
                    system="",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=8192,
                )
                if not response:
                    logger.warning("API 返回空文本 (attempt %s)", attempt + 1)
                    continue
                updates = _safe_parse_json(response)
                if updates and all(k in updates for k in ["progress", "diary", "wechat_unread"]):
                    return updates, None
                logger.warning("JSON 解析后缺少必要字段 (attempt %s)", attempt + 1)
                last_error = "JSON 解析后缺少必要字段"
            except Exception as exc:
                logger.error("课后更新 API 调用失败 (attempt %s): %s", attempt + 1, exc)
                last_error = str(exc)
        return None, last_error

    def _backup_files(self, files_def: list[dict[str, Any]]) -> tuple[Path, list[tuple[Path, Path]]]:
        backup_dir = self._backups_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir.mkdir(parents=True, exist_ok=True)
        backed_up = []
        for file_def in files_def:
            path = file_def["path"]
            if path and path.exists():
                backup_path = backup_dir / path.name
                shutil.copy2(path, backup_path)
                backed_up.append((path, backup_path))
        return backup_dir, backed_up

    def _write_updates(
        self,
        files_def: list[dict[str, Any]],
        updates: dict[str, str],
        backed_up: list[tuple[Path, Path]],
        backup_dir: Path,
    ) -> list[str] | None:
        updated = []
        for file_def in files_def:
            key = file_def["key"]
            path = file_def["path"]
            new_content = updates.get(key)
            if new_content is None or path is None:
                continue
            try:
                if key in APPEND_KEYS:
                    existing = path.read_text(encoding="utf-8") if path.exists() else ""
                    if existing and not existing.endswith("\n"):
                        existing += "\n"
                    path.write_text(existing + new_content, encoding="utf-8")
                else:
                    path.write_text(new_content, encoding="utf-8")
                if file_def["validate"](new_content):
                    updated.append(key)
                    logger.info("已更新 %s", path.name)
                else:
                    raise ValueError(f"验证失败: {key}")
            except Exception as exc:
                logger.error("更新 %s 失败: %s", path.name, exc)
                _rollback(backed_up)
                shutil.rmtree(backup_dir, ignore_errors=True)
                self._lesson_manager.update_end_job("failed", error=str(exc))
                return None
        return updated

    def _cleanup_backups(self) -> None:
        if not self._backups_dir.exists():
            return
        backups = sorted(self._backups_dir.iterdir(), key=lambda p: p.name, reverse=True)
        for old_backup in backups[10:]:
            if old_backup.is_dir():
                shutil.rmtree(old_backup)


def _safe_parse_json(text: str) -> dict[str, str] | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    json_object = re.search(r"\{.*\}", text, re.DOTALL)
    if json_object:
        try:
            return json.loads(json_object.group(0))
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _rollback(backed_up: list[tuple[Path, Path]]) -> None:
    for original_path, backup_path in backed_up:
        with contextlib.suppress(Exception):
            shutil.copy2(backup_path, original_path)
