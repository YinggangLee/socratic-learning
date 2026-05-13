import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from post_lesson import _format_conversation, _build_update_prompt


class TestFormatConversation:
    def test_formats_user_and_assistant_roles(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi back"},
        ]
        result = _format_conversation(msgs)
        assert "学生" in result
        assert "老师" in result
        assert "hello" in result
        assert "hi back" in result

    def test_truncates_long_content(self):
        msgs = [{"role": "user", "content": "x" * 600}]
        result = _format_conversation(msgs)
        assert len(result) < 700  # truncated to 500 + formatting

    def test_limits_to_last_30_messages(self):
        msgs = [{"role": "user", "content": f"msg{i}"} for i in range(40)]
        result = _format_conversation(msgs)
        # First few messages should be omitted
        assert "msg0" not in result
        assert "msg39" in result

    def test_empty_list(self):
        result = _format_conversation([])
        assert result == ""


class TestBuildUpdatePrompt:
    def test_returns_string_with_teacher_name(self):
        result = _build_update_prompt(
            teacher_display="三月七",
            conversation_text="conv",
            progress_text="prog",
            diary_text="diary",
            wechat_text="wx",
            persona_text="persona",
        )
        assert isinstance(result, str)
        assert "三月七" in result

    def test_includes_conversation_text(self):
        result = _build_update_prompt(
            teacher_display="甘雨",
            conversation_text="UNIQUE_CONV_123",
            progress_text="",
            diary_text="",
            wechat_text="",
            persona_text="",
        )
        assert "UNIQUE_CONV_123" in result

    def test_includes_archive_and_revision_when_provided(self):
        result = _build_update_prompt(
            teacher_display="刻晴",
            conversation_text="c",
            progress_text="p",
            diary_text="d",
            wechat_text="w",
            persona_text="pp",
            archive_text="OLD_ARCHIVE",
            revision_text="OLD_REVISION",
        )
        assert "OLD_ARCHIVE" in result
        assert "OLD_REVISION" in result

    def test_prompt_asks_for_json_output(self):
        result = _build_update_prompt("三月七", "c", "p", "d", "w", "pp")
        assert "JSON" in result
