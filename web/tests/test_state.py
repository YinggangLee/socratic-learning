import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import ACTIVE_SESSION_FILE
from state import LessonState, get_active_session, create_session, clear_session


def _cleanup_session_file():
    clear_session()
    if ACTIVE_SESSION_FILE.exists():
        ACTIVE_SESSION_FILE.unlink()


class TestLessonState:
    def setup_method(self):
        _cleanup_session_file()

    def teardown_method(self):
        _cleanup_session_file()

    def test_init_basic_fields(self):
        state = LessonState("s1", "march7", "三月七")
        assert state.session_id == "s1"
        assert state.teacher_name == "march7"
        assert state.teacher_display == "三月七"
        assert state.lesson_started_at is not None

    def test_add_message(self):
        state = LessonState("s2", "ganyu", "甘雨")
        state.add_message("user", "hello")
        state.add_message("assistant", "hi back")
        assert len(state.messages) == 2
        assert state.messages[0].role == "user"
        assert state.messages[0].content == "hello"
        assert state.messages[1].role == "assistant"

    def test_to_dict(self):
        state = LessonState("s3", "keqing", "刻晴")
        state.add_message("user", "q")
        d = state.to_dict()
        assert d["session_id"] == "s3"
        assert d["teacher_name"] == "keqing"
        assert len(d["messages"]) == 1

    def test_end_job_lifecycle(self):
        state = LessonState("s4", "march7", "三月七")
        assert state.get_end_job_status() is None
        state.start_end_job("job123")
        assert state.get_end_job_status()["status"] == "processing"
        state.update_end_job("done", updated_files=["a", "b"])
        assert state.get_end_job_status()["status"] == "done"
        assert state.get_end_job_status()["updated_files"] == ["a", "b"]

    def test_update_end_job_with_error(self):
        state = LessonState("s5", "march7", "三月七")
        state.start_end_job("job456")
        state.update_end_job("failed", error="something broke")
        assert state.get_end_job_status()["status"] == "failed"
        assert "something broke" in state.get_end_job_status()["error"]


class TestSessionManagement:
    def setup_method(self):
        _cleanup_session_file()

    def teardown_method(self):
        _cleanup_session_file()

    def test_get_session_returns_none_when_cleared(self):
        clear_session()
        assert get_active_session() is None

    def test_create_session(self):
        s = create_session("ganyu", "甘雨")
        assert s is not None
        assert s.teacher_name == "ganyu"
        assert get_active_session() is not None

    def test_clear_session(self):
        create_session("march7", "三月七")
        clear_session()
        assert get_active_session() is None

    def test_create_after_clear(self):
        s1 = create_session("march7", "三月七")
        clear_session()
        s2 = create_session("keqing", "刻晴")
        assert s2.session_id != s1.session_id
        assert s2.teacher_name == "keqing"
