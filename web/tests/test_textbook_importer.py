import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from textbook_importer import (
    slugify_name, create_textbook_dirs, import_markdown_file,
)


class TestSlugifyName:
    def test_basic(self):
        assert slugify_name("Building Effective Agents") == "building-effective-agents"

    def test_special_chars(self):
        assert slugify_name("Hello! World?") == "hello-world"


class TestCreateDirs:
    def test_creates_paths(self, tmp_path):
        content, progress = create_textbook_dirs("Test Book", tmp_path)
        assert str(content).endswith(".md")
        assert str(progress).endswith(".md")

    def test_override_id(self, tmp_path):
        content, progress = create_textbook_dirs("Some Name", tmp_path, override_id="custom-id")
        assert "custom-id" in str(content)
        assert content.parent.exists()

    def test_writes_progress_template(self, tmp_path):
        _, progress = create_textbook_dirs("My Book", tmp_path)
        text = progress.read_text()
        assert "# 学习进度" in text
        assert "| 日期 |" in text


class TestImportMarkdown:
    def test_import_valid_file(self, tmp_path):
        src = tmp_path / "source.md"
        src.write_text("# Hello\n\nWorld")
        dest = tmp_path / "dest.md"
        assert import_markdown_file(src, dest) is True
        assert dest.read_text() == "# Hello\n\nWorld"

    def test_import_empty_file_fails(self, tmp_path):
        src = tmp_path / "empty.md"
        src.write_text("")
        dest = tmp_path / "dest.md"
        assert import_markdown_file(src, dest) is False
