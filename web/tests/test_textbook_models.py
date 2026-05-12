import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from textbook_models import (
    TextbookRecord, TextbookCreateRequest, TextbookStatusRequest,
    ImportStatus, TextbookStatus,
)


class TestTextbookRecord:
    def test_valid_record(self):
        r = TextbookRecord(
            id="building-effective-agents",
            name="Building Effective Agents",
            content_path="textbook/building-effective-agents.md",
            source_type="url",
            progress_path="teacher/progress/building-effective-agents.md",
            status="active",
            import_status="ready",
        )
        assert r.id == "building-effective-agents"
        assert r.status == TextbookStatus.active
        assert r.import_status == ImportStatus.ready

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError):
            TextbookRecord(
                id="x", name="X", content_path="x.md",
                source_type="url", progress_path="p.md",
                status="invalid", import_status="ready",
            )

    def test_active_requires_ready_import(self):
        with pytest.raises(ValueError):
            TextbookRecord(
                id="x", name="X", content_path="x.md",
                source_type="url", progress_path="p.md",
                status="active", import_status="pending",
            )

    def test_defaults_to_inactive_and_pending(self):
        r = TextbookRecord(
            id="x", name="X", content_path="x.md",
            source_type="url", progress_path="p.md",
        )
        assert r.status == TextbookStatus.inactive
        assert r.import_status == ImportStatus.pending


class TestTextbookCreateRequest:
    def test_minimal_fields(self):
        r = TextbookCreateRequest(name="New Book", source_type="url", source_ref="https://example.com")
        assert r.name == "New Book"

    def test_generates_slug_id(self):
        r = TextbookCreateRequest(name="Building Effective Agents!", source_type="url")
        assert r._generate_id() == "building-effective-agents"

    def test_generates_id_from_chinese(self):
        r = TextbookCreateRequest(name="  Hello   World  ", source_type="file_md")
        assert r._generate_id() == "hello-world"

    def test_default_id_for_empty(self):
        r = TextbookCreateRequest(name="!!!", source_type="url")
        assert r._generate_id() == "untitled"
