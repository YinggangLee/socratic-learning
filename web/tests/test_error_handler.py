import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from error_handler import safe_parse_json


class TestSafeParseJson:
    def test_parses_valid_json(self):
        result = safe_parse_json('{"a": 1, "b": "hello"}')
        assert result == {"a": 1, "b": "hello"}

    def test_extracts_from_markdown_code_block(self):
        result = safe_parse_json('```json\n{"x": 99}\n```')
        assert result == {"x": 99}

    def test_extracts_from_code_block_without_lang(self):
        result = safe_parse_json('```\n{"y": "ok"}\n```')
        assert result == {"y": "ok"}

    def test_extracts_first_json_object(self):
        result = safe_parse_json('some text {"k": "v"} more text')
        assert result == {"k": "v"}

    def test_returns_none_for_invalid(self):
        result = safe_parse_json('not json at all')
        assert result is None

    def test_handles_nested_braces_correctly(self):
        result = safe_parse_json('{"outer": {"inner": 1, "deep": [1,2,3]}}')
        assert result == {"outer": {"inner": 1, "deep": [1, 2, 3]}}

    def test_empty_string_returns_none(self):
        result = safe_parse_json("")
        assert result is None
