import re
from pathlib import Path
from config import TEACHER_DIR, get_active_textbook, TEXTBOOK_DIR, TEACHER_NAMES, TEACHER_DISPLAY
from token_budget import budget_check, estimate_tokens


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _get_active_progress() -> tuple[Path | None, str]:
    """Return (progress_file_path, textbook_name) for the active textbook.
    Uses store's explicit progress_path, falls back to first .md in progress/"""
    _, progress_path = get_active_textbook()
    if progress_path and progress_path.exists():
        return progress_path, progress_path.stem.replace("-", " ").title()
    progress_dir = TEACHER_DIR / "progress"
    if not progress_dir.exists():
        return None, ""
    for f in sorted(progress_dir.iterdir()):
        if f.suffix == ".md":
            return f, f.stem.replace("-", " ").title()
    return None, ""


def _determine_teacher(progress_text: str) -> str:
    """Extract next teacher's English name from progress file."""
    for line in progress_text.split("\n"):
        if "下一位授课老师" in line or "下一位授课教师" in line:
            for t in TEACHER_NAMES:
                if t in line.lower():
                    return t
            # Check display names
            for eng, chn in TEACHER_DISPLAY.items():
                if chn in line:
                    return eng
    # Default: first teacher
    return "march7"


def _get_teacher_order_until_current(current_teacher: str) -> list[str]:
    """Return the ordered list of teachers who have taught up to (but not including) current."""
    try:
        idx = TEACHER_NAMES.index(current_teacher)
    except ValueError:
        idx = 0
    # Previously taught teachers are those before current in the cycle
    seen = []
    for i in range(idx):
        seen.append(TEACHER_NAMES[i])
    return seen


def _summarize_recent(filepath: Path, max_chars: int = 2000) -> str:
    """Read last ~max_chars characters of a file for context summary."""
    text = _read(filepath)
    if len(text) <= max_chars:
        return text
    return "…(earlier content omitted)…\n\n" + text[-max_chars:]


def _extract_textbook_section(progress_text: str) -> str:
    """Extract the textbook section relevant to current progress."""
    textbook_path, _ = get_active_textbook()
    textbook = _read(textbook_path)
    if not textbook:
        return "（教材未找到）"

    # Try to find the current chapter from progress
    current_chapter = ""
    for line in progress_text.split("\n"):
        if "当前章节" in line or "当前内容" in line:
            current_chapter = line.split("：")[-1].split(":")[-1].strip()
            break

    if not current_chapter:
        # Return first few sections of textbook
        return textbook[:8000]

    # Find the section in the textbook matching current_chapter
    section_start = textbook.find(current_chapter)
    if section_start == -1:
        # Try to find a heading that contains the chapter name
        for heading in re.findall(r'^#{1,3}\s+.+$', textbook, re.MULTILINE):
            if current_chapter.lower() in heading.lower():
                section_start = textbook.find(heading)
                break

    if section_start == -1:
        return textbook[:8000]

    # Return from that section onward, capped at 12000 chars
    section_text = textbook[section_start:]
    if len(section_text) > 12000:
        # Try to cut at next ### or ## boundary
        cutoff = section_text.find("\n## ", 500)
        if cutoff == -1:
            cutoff = section_text.find("\n### ", 500)
        if cutoff == -1:
            cutoff = 12000
        section_text = section_text[:cutoff]

    return section_text


def build_system_prompt(
    teacher_name: str | None = None,
    chat_history: str = "",
    remaining_minutes: int | None = None,
) -> str:
    """
    Build the full system prompt for a given teacher and context.
    If teacher_name is None, determines from progress.
    """
    # Determine active textbook and progress
    progress_file, textbook_name = _get_active_progress()
    progress_text = _read(progress_file) if progress_file else ""
    current_teacher = teacher_name or _determine_teacher(progress_text)

    # Read essential files
    system_rules = _read(TEACHER_DIR / "system.md") + "\n\n" + _read(TEACHER_DIR / "system_detail.md")
    learner_profile = _read(TEACHER_DIR / "learner_profile.md")
    teacher_persona = _read(TEACHER_DIR / f"{current_teacher}.md")
    wechat_group = _summarize_recent(TEACHER_DIR / "wechat_group.md", 1500)
    wechat_unread = _summarize_recent(TEACHER_DIR / "wechat_unread.md", 1500)
    diary = _summarize_recent(TEACHER_DIR / "diary.md", 1500)
    textbook_section = _extract_textbook_section(progress_text)

    # Build teaching instruction
    seen_teachers = _get_teacher_order_until_current(current_teacher)
    teaching_instruction = f"""## 当前教学状态
- 教材：{textbook_name}
- 当前授课老师：{TEACHER_DISPLAY.get(current_teacher, current_teacher)}
- 之前的授课老师：{', '.join(TEACHER_DISPLAY.get(t, t) for t in seen_teachers) if seen_teachers else '（这是第一节课）'}
- 教学进度：
{progress_text}

## 你的任务
你是{TEACHER_DISPLAY.get(current_teacher, current_teacher)}。请严格遵循你的教师人设文档，以苏格拉底教学法（全程问题引导、学生自主推理）进行教学。严格遵守教学规则和表达格式规范。"""

    if remaining_minutes is not None and remaining_minutes <= 5:
        teaching_instruction += f"\n\n**⚠️ 课时提醒：本节课还剩约 {remaining_minutes} 分钟，请准备收尾总结。**"

    # Assemble parts for budget check
    parts = {
        "system_rules": system_rules,
        "teaching_instruction": teaching_instruction,
        "teacher_persona": teacher_persona,
        "textbook_chapter": f"## 教材内容（当前相关章节）\n\n{textbook_section}",
        "chat_history": chat_history,
        "wechat_diary_summary": f"## 微信群最近聊天\n\n{wechat_group}\n\n{wechat_unread}\n\n## 学习日记（最近）\n\n{diary}",
        "learner_profile": learner_profile,
    }

    # Apply token budget
    parts = budget_check(parts)

    # Assemble final prompt
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


def build_chat_messages(
    teacher_name: str,
    messages: list[dict],
    remaining_minutes: int | None = None,
) -> tuple[str, list[dict]]:
    """
    Build system prompt and message list for a chat API call.
    Returns (system_prompt, api_messages).
    """
    # Format chat history from previous messages
    history_parts = []
    for m in messages[-20:]:  # last 20 messages max in prompt
        role_label = "学生" if m["role"] == "user" else TEACHER_DISPLAY.get(teacher_name, teacher_name)
        history_parts.append(f"**{role_label}**：{m['content']}")
    chat_history = "## 对话历史\n\n" + "\n\n".join(history_parts) if history_parts else ""

    system_prompt = build_system_prompt(
        teacher_name=teacher_name,
        chat_history=chat_history,
        remaining_minutes=remaining_minutes,
    )

    # Build API messages: system + all conversation messages
    api_messages = []
    for m in messages:
        role = m["role"]
        if role == "user":
            api_messages.append({"role": "user", "content": m["content"]})
        else:
            api_messages.append({"role": "assistant", "content": m["content"]})

    return system_prompt, api_messages


def build_start_prompt() -> tuple[str, str, str]:
    """
    Build the prompt for starting a new lesson.
    Returns (teacher_name, teacher_display, system_prompt_with_opening_instruction).
    """
    progress_file, _ = _get_active_progress()
    progress_text = _read(progress_file) if progress_file else ""
    teacher_name = _determine_teacher(progress_text)

    system_prompt = build_system_prompt(teacher_name=teacher_name)

    # Append opening instruction
    opening_instruction = f"""
你现在开始上课。你是{TEACHER_DISPLAY.get(teacher_name, teacher_name)}。
请向学生打招呼（寒暄、回顾上节课内容、引出本节课主题），
自然地开始今天的教学。先做开场白即可，不必展开完整教学。
确保开场白符合你的人设和教学风格。"""
    full_prompt = system_prompt + opening_instruction

    return teacher_name, TEACHER_DISPLAY.get(teacher_name, teacher_name), full_prompt
