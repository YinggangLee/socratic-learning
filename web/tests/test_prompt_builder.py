import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from prompt_builder import _determine_teacher, _get_active_progress


class TestDetermineTeacher:
    def test_extracts_march7(self):
        text = "下一位授课老师：三月七 (march7)"
        assert _determine_teacher(text) == "march7"

    def test_extracts_ganyu(self):
        text = "下一位授课教师：甘雨"
        assert _determine_teacher(text) == "ganyu"

    def test_extracts_keqing(self):
        text = "...下一位授课老师是 刻晴，明天见"
        assert _determine_teacher(text) == "keqing"

    def test_defaults_to_march7_when_not_found(self):
        text = "今天天气很好"
        assert _determine_teacher(text) == "march7"

    def test_defaults_to_march7_when_empty(self):
        assert _determine_teacher("") == "march7"


class TestGetActiveProgress:
    def test_returns_tuple_of_path_and_str(self):
        result = _get_active_progress()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_progress_path_is_valid(self):
        path, name = _get_active_progress()
        if path is not None:
            assert path.suffix == ".md"
            assert len(name) > 0
