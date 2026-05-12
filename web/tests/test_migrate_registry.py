import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from migrate_registry import migrate_from_legacy


def test_migrate_single_md_textbook(tmp_path):
    textbook_dir = tmp_path / "textbook"
    textbook_dir.mkdir()
    (textbook_dir / "textbook_registry.md").write_text(
        "| 教材名称 | 路径 | 来源 | 状态 |\n"
        "|----------|------|------|------|\n"
        "| Building Effective Agents | textbook/building-effective-agents.md | "
        "URL: https://www.anthropic.com/engineering/building-effective-agents | active |\n"
    )
    (textbook_dir / "building-effective-agents.md").write_text("# Test")
    json_path = textbook_dir / "registry.json"
    migrate_from_legacy(textbook_dir, json_path)
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data["active_textbook_id"] == "building-effective-agents"
    assert len(data["textbooks"]) == 1
    assert data["textbooks"][0]["progress_path"] == "teacher/progress/building-effective-agents.md"


def test_migrate_directory_textbook(tmp_path):
    textbook_dir = tmp_path / "textbook"
    textbook_dir.mkdir()
    (textbook_dir / "textbook_registry.md").write_text(
        "| 教材名称 | 路径 | 来源 | 状态 |\n"
        "|----------|------|------|------|\n"
        "| Google Whitepapers | textbook/google-ai-agent-whitepapers/ | uploaded | active |\n"
    )
    subdir = textbook_dir / "google-ai-agent-whitepapers"
    subdir.mkdir()
    (subdir / "01-intro.md").write_text("# Intro")
    json_path = textbook_dir / "registry.json"
    migrate_from_legacy(textbook_dir, json_path)
    data = json.loads(json_path.read_text())
    assert data["active_textbook_id"] == "google-ai-agent-whitepapers"
    assert "01-intro.md" in data["textbooks"][0]["content_path"]


def test_migrate_skips_inactive_correctly(tmp_path):
    textbook_dir = tmp_path / "textbook"
    textbook_dir.mkdir()
    (textbook_dir / "textbook_registry.md").write_text(
        "| 教材名称 | 路径 | 来源 | 状态 |\n"
        "|----------|------|------|------|\n"
        "| Inactive Book | textbook/inactive.md | file | inactive |\n"
    )
    (textbook_dir / "inactive.md").write_text("# Inactive")
    json_path = textbook_dir / "registry.json"
    migrate_from_legacy(textbook_dir, json_path)
    data = json.loads(json_path.read_text())
    assert data["active_textbook_id"] is None
    assert data["textbooks"][0]["status"] == "inactive"
