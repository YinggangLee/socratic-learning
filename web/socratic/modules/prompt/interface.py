from typing import Protocol
from .models import PromptContext, BuiltPrompt


class PromptBuilder(Protocol):
    def build_start_prompt(self) -> tuple[str, str, str]: ...
    # Returns (teacher_name, teacher_display, system_prompt)

    def build_chat_messages(self, teacher_name: str, messages: list[dict], remaining_minutes: int | None = None) -> tuple[str, list[dict]]: ...
    # Returns (system_prompt, api_messages)
