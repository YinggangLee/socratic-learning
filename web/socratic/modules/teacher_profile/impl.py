"""Teacher profile repository implementation — reads from teacher/*.md files."""

from pathlib import Path


class MarkdownTeacherProfileRepository:
    def __init__(self, teacher_dir: Path, teacher_names: list[str], teacher_display: dict[str, str]):
        self._dir = teacher_dir
        self._names = teacher_names
        self._display = teacher_display

    def get_teacher_names(self) -> list[str]:
        return list(self._names)

    def get_teacher_display(self, name: str) -> str:
        return self._display.get(name, name)

    def get_persona(self, name: str) -> str:
        return self._read(self._dir / f"{name}.md")

    def get_diary_recent(self, max_chars: int = 5000) -> str:
        return self._summarize(self._dir / "diary.md", max_chars)

    def get_wechat_context(self) -> str:
        group = self._summarize(self._dir / "wechat_group.md", 1500)
        unread = self._summarize(self._dir / "wechat_unread.md", 1500)
        return f"{group}\n\n{unread}"

    def determine_next_teacher(self, progress_text: str) -> str:
        for line in progress_text.split("\n"):
            if "下一位授课老师" in line or "下一位授课教师" in line:
                for t in self._names:
                    if t in line.lower():
                        return t
                for eng, chn in self._display.items():
                    if chn in line:
                        return eng
        return self._names[0]

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def _summarize(self, path: Path, max_chars: int) -> str:
        text = self._read(path)
        if len(text) <= max_chars:
            return text
        return "…(earlier content omitted)…\n\n" + text[-max_chars:]
