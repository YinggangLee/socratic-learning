"""Prompt builder implementation."""

from pathlib import Path
import re

import tiktoken

enc = tiktoken.get_encoding("cl100k_base")

# Priority order (highest first) for token budget trimming
PROMPT_PART_PRIORITY = {
    "system_rules": 1,
    "teaching_instruction": 2,
    "teacher_persona": 3,
    "textbook_chapter": 4,
    "chat_history": 5,
    "wechat_diary_summary": 6,
    "learner_profile": 7,
}


def _estimate_tokens(text: str) -> int:
    return len(enc.encode(text))


class TokenBudgetPromptBuilder:
    def __init__(
        self,
        teacher_repo,  # TeacherProfileRepository
        textbook_catalog,  # TextbookCatalog
        storage,  # FileStorage
        teacher_dir: Path,
        teacher_names: list[str],
        teacher_display: dict[str, str],
        available_budget: int = 987712,
        max_tokens_response: int = 4096,
    ):
        self._teachers = teacher_repo
        self._catalog = textbook_catalog
        self._storage = storage
        self._teacher_dir = teacher_dir
        self._names = teacher_names
        self._display = teacher_display
        self._budget = available_budget
        self._max_resp = max_tokens_response

    def build_start_prompt(self) -> tuple[str, str, str]:
        _progress_file, progress_text = self._get_progress()
        teacher_name = self._teachers.determine_next_teacher(progress_text)

        system_prompt = self._build_system_prompt(
            teacher_name=teacher_name,
            progress_text=progress_text,
            chat_history="",
        )

        opening_instruction = f"""
你现在开始上课。你是{self._display.get(teacher_name, teacher_name)}。
请向学生打招呼（寒暄、回顾上节课内容、引出本节课主题），
自然地开始今天的教学。先做开场白即可，不必展开完整教学。
确保开场白符合你的人设和教学风格。"""

        return teacher_name, self._display.get(teacher_name, teacher_name), system_prompt + opening_instruction

    def build_chat_messages(
        self, teacher_name: str, messages: list[dict], remaining_minutes: int | None = None
    ) -> tuple[str, list[dict]]:
        # Format chat history
        history_parts = []
        for m in messages[-20:]:
            role_label = "学生" if m["role"] == "user" else self._display.get(teacher_name, teacher_name)
            history_parts.append(f"**{role_label}**：{m['content']}")
        chat_history = "## 对话历史\n\n" + "\n\n".join(history_parts) if history_parts else ""

        system_prompt = self._build_system_prompt(
            teacher_name=teacher_name,
            progress_text=self._get_progress_text(),
            chat_history=chat_history,
            remaining_minutes=remaining_minutes,
        )

        api_messages = []
        for m in messages:
            api_messages.append({"role": m["role"], "content": m["content"]})

        return system_prompt, api_messages

    def _build_system_prompt(
        self, teacher_name: str, progress_text: str, chat_history: str, remaining_minutes: int | None = None
    ) -> str:
        system_rules = (
            self._storage.read_text(self._teacher_dir / "system.md")
            + "\n\n"
            + self._storage.read_text(self._teacher_dir / "system_detail.md")
        )
        learner_profile = self._storage.read_text(self._teacher_dir / "learner_profile.md")
        teacher_persona = self._teachers.get_persona(teacher_name)
        wechat_context = self._teachers.get_wechat_context()
        diary = self._teachers.get_diary_recent(1500)
        textbook_section = self._get_textbook_section(progress_text)
        textbook_name = self._get_textbook_name()

        seen_teachers = self._get_teacher_order(teacher_name)
        teaching_instruction = f"""## 当前教学状态
- 教材：{textbook_name}
- 当前授课老师：{self._display.get(teacher_name, teacher_name)}
- 之前的授课老师：{", ".join(self._display.get(t, t) for t in seen_teachers) if seen_teachers else "（这是第一节课）"}
- 教学进度：
{progress_text}

## 你的任务
你是{self._display.get(teacher_name, teacher_name)}。请严格遵循你的教师人设文档，以苏格拉底教学法（全程问题引导、学生自主推理）进行教学。严格遵守教学规则和表达格式规范。"""

        if remaining_minutes is not None and remaining_minutes <= 5:
            teaching_instruction += f"\n\n**⚠️ 课时提醒：本节课还剩约 {remaining_minutes} 分钟，请准备收尾总结。**"

        parts = {
            "system_rules": system_rules,
            "teaching_instruction": teaching_instruction,
            "teacher_persona": teacher_persona,
            "textbook_chapter": f"## 教材内容（当前相关章节）\n\n{textbook_section}",
            "chat_history": chat_history,
            "wechat_diary_summary": f"## 微信群最近聊天\n\n{wechat_context}\n\n## 学习日记（最近）\n\n{diary}",
            "learner_profile": learner_profile,
        }

        parts = self._budget_check(parts)
        sections = [
            parts.get("system_rules", ""),
            parts.get("teacher_persona", ""),
            parts.get("learner_profile", ""),
            parts.get("teaching_instruction", ""),
            parts.get("textbook_chapter", ""),
            parts.get("wechat_diary_summary", ""),
            parts.get("chat_history", ""),
        ]
        return "\n\n---\n\n".join(s for s in sections if s)

    def _get_progress(self) -> tuple[Path | None, str]:
        try:
            active = self._catalog.get_active()
            if active:
                progress_path = self._teacher_dir.parent / active.progress_path
                if progress_path.exists():
                    return progress_path, progress_path.read_text(encoding="utf-8")
        except Exception:
            pass

        # Legacy fallback
        progress_dir = self._teacher_dir / "progress"
        if progress_dir.exists():
            for f in sorted(progress_dir.iterdir()):
                if f.suffix == ".md":
                    return f, f.read_text(encoding="utf-8")
        return None, ""

    def _get_progress_text(self) -> str:
        _, text = self._get_progress()
        return text

    def _get_textbook_name(self) -> str:
        try:
            active = self._catalog.get_active()
            if active:
                return active.name
        except Exception:
            pass
        progress_file, _ = self._get_progress()
        if progress_file:
            return progress_file.stem.replace("-", " ").title()
        return ""

    def _get_textbook_section(self, progress_text: str) -> str:
        try:
            active = self._catalog.get_active()
            if active:
                textbook_path = self._teacher_dir.parent / active.content_path
                return self._extract_section(self._storage.read_text(textbook_path), progress_text)
        except Exception:
            pass
        # Legacy fallback
        legacy = self._teacher_dir.parent / "textbook" / "building-effective-agents.md"
        if legacy.exists():
            return self._extract_section(self._storage.read_text(legacy), progress_text)
        return "（教材未找到）"

    def _extract_section(self, textbook: str, progress_text: str) -> str:
        if not textbook:
            return "（教材未找到）"

        current_chapter = ""
        for line in progress_text.split("\n"):
            if "当前章节" in line or "当前内容" in line:
                current_chapter = line.split("：")[-1].split(":")[-1].strip()
                break

        if not current_chapter:
            return textbook[:8000]

        section_start = textbook.find(current_chapter)
        if section_start == -1:
            for heading in re.findall(r"^#{1,3}\s+.+$", textbook, re.MULTILINE):
                if current_chapter.lower() in heading.lower():
                    section_start = textbook.find(heading)
                    break

        if section_start == -1:
            return textbook[:8000]

        section_text = textbook[section_start:]
        if len(section_text) > 12000:
            cutoff = section_text.find("\n## ", 500)
            if cutoff == -1:
                cutoff = section_text.find("\n### ", 500)
            if cutoff == -1:
                cutoff = 12000
            section_text = section_text[:cutoff]

        return section_text

    def _get_teacher_order(self, current: str) -> list[str]:
        try:
            idx = self._names.index(current)
        except ValueError:
            idx = 0
        return [self._names[i] for i in range(idx)]

    def _budget_check(self, parts: dict[str, str]) -> dict[str, str]:
        total = _estimate_tokens("".join(parts.values()))
        if total + self._max_resp <= self._budget:
            return parts

        ordered = sorted(parts.items(), key=lambda kv: PROMPT_PART_PRIORITY.get(kv[0], 99))
        result = dict(parts)
        for name, _ in reversed(ordered):
            if _estimate_tokens("".join(result.values())) + self._max_resp <= self._budget:
                break
            if name not in ("system_rules", "teaching_instruction"):
                result.pop(name, None)

        if "chat_history" in result:
            while _estimate_tokens("".join(result.values())) + self._max_resp > self._budget:
                lines = result["chat_history"].split("\n")
                if len(lines) <= 2:
                    result.pop("chat_history", None)
                    break
                result["chat_history"] = "\n".join(lines[4:]) if len(lines) > 4 else ""

        return result
