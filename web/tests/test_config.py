import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from config import get_active_textbook, TEXTBOOK_DIR


class TestGetActiveTextbook:
    def test_returns_tuple_of_paths_or_none(self):
        content, progress = get_active_textbook()
        assert content is None or isinstance(content, Path)
        assert progress is None or isinstance(progress, Path)

    def test_content_path_exists_when_not_none(self):
        content, _ = get_active_textbook()
        if content is not None:
            assert content.exists()

    def test_content_path_under_textbook_dir(self):
        content, _ = get_active_textbook()
        if content is not None:
            assert str(TEXTBOOK_DIR) in str(content)

    def test_content_path_has_md_extension(self):
        content, _ = get_active_textbook()
        if content is not None:
            assert content.suffix == ".md"

    def test_progress_path_under_teacher_progress(self):
        _, progress = get_active_textbook()
        if progress is not None:
            assert "teacher/progress" in str(progress)
            assert progress.suffix == ".md"

    def test_falls_back_to_default_when_no_active(self):
        content, progress = get_active_textbook()
        # Should always return at least a fallback content path
        assert content is not None or progress is not None
