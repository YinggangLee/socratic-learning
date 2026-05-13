from dataclasses import dataclass, field


@dataclass
class PromptContext:
    teacher_name: str
    teacher_display: str
    progress_text: str = ""
    textbook_text: str = ""
    remaining_minutes: int | None = None


@dataclass
class BuiltPrompt:
    system_prompt: str
    messages: list[dict] = field(default_factory=list)
