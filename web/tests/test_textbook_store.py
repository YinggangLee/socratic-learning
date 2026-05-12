import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from textbook_store import TextbookStore
from textbook_models import TextbookRecord, TextbookStatus, ImportStatus


@pytest.fixture
def tmp_store():
    with tempfile.TemporaryDirectory() as d:
        store = TextbookStore(registry_path=Path(d) / "registry.json")
        yield store


class TestTextbookStore:
    def test_init_creates_empty_registry(self, tmp_store):
        assert tmp_store.list_all() == []

    def test_add_textbook(self, tmp_store):
        r = tmp_store.add(
            name="Test Book", source_type="file_md",
            content_path="textbook/imported/test-book.md",
            progress_path="teacher/progress/test-book.md",
            import_status=ImportStatus.ready,
        )
        assert r.id == "test-book"
        assert r.status == TextbookStatus.inactive
        assert tmp_store.get("test-book") is not None

    def test_set_active(self, tmp_store):
        a = tmp_store.add(name="A", source_type="file_md",
                          content_path="a.md", progress_path="pa.md", import_status=ImportStatus.ready)
        b = tmp_store.add(name="B", source_type="file_md",
                          content_path="b.md", progress_path="pb.md", import_status=ImportStatus.ready)
        tmp_store.set_active(a.id)
        assert tmp_store.get(a.id).status == TextbookStatus.active
        assert tmp_store.get(b.id).status == TextbookStatus.inactive
        tmp_store.set_active(b.id)
        assert tmp_store.get(a.id).status == TextbookStatus.inactive
        assert tmp_store.get(b.id).status == TextbookStatus.active

    def test_cannot_activate_non_ready(self, tmp_store):
        r = tmp_store.add(name="X", source_type="url", content_path="x.md",
                          progress_path="px.md", import_status=ImportStatus.failed)
        with pytest.raises(ValueError, match="import_status"):
            tmp_store.set_active(r.id)

    def test_soft_delete_inactive(self, tmp_store):
        r = tmp_store.add(name="Del", source_type="file_md",
                          content_path="d.md", progress_path="pd.md", import_status=ImportStatus.ready)
        tmp_store.soft_delete(r.id)
        assert tmp_store.get(r.id).status == TextbookStatus.deleted

    def test_cannot_delete_active(self, tmp_store):
        r = tmp_store.add(name="ActiveDel", source_type="file_md",
                          content_path="ad.md", progress_path="pad.md", import_status=ImportStatus.ready)
        tmp_store.set_active(r.id)
        with pytest.raises(ValueError, match="active"):
            tmp_store.soft_delete(r.id)

    def test_restore_deleted(self, tmp_store):
        r = tmp_store.add(name="Rest", source_type="file_md",
                          content_path="r.md", progress_path="pr.md", import_status=ImportStatus.ready)
        tmp_store.soft_delete(r.id)
        tmp_store.restore(r.id)
        assert tmp_store.get(r.id).status == TextbookStatus.inactive

    def test_list_excludes_deleted_by_default(self, tmp_store):
        tmp_store.add(name="Visible", source_type="file_md",
                      content_path="v.md", progress_path="pv.md", import_status=ImportStatus.ready)
        d = tmp_store.add(name="Hidden", source_type="file_md",
                          content_path="h.md", progress_path="ph.md", import_status=ImportStatus.ready)
        tmp_store.soft_delete(d.id)
        visible = tmp_store.list_all()
        assert len(visible) == 1
        assert visible[0].name == "Visible"
        all_items = tmp_store.list_all(show_deleted=True)
        assert len(all_items) == 2

    def test_get_active_paths(self, tmp_store):
        tmp_store.add(name="A", source_type="file_md",
                      content_path="a.md", progress_path="pa.md", import_status=ImportStatus.ready)
        b = tmp_store.add(name="B", source_type="file_md",
                          content_path="b.md", progress_path="pb.md", import_status=ImportStatus.ready)
        tmp_store.set_active(b.id)
        content_path, progress_path = tmp_store.get_active_paths()
        assert content_path == b.content_path
        assert progress_path == b.progress_path

    def test_get_active_returns_none_when_none(self, tmp_store):
        assert tmp_store.get_active_paths() == (None, None)

    def test_atomic_write(self, tmp_store):
        r = tmp_store.add(name="Persist", source_type="file_md",
                          content_path="p.md", progress_path="pp.md", import_status=ImportStatus.ready)
        # Reload from disk
        store2 = TextbookStore(registry_path=tmp_store._registry_path)
        assert store2.get(r.id) is not None
        assert store2.get(r.id).name == "Persist"

    def test_mark_completed(self, tmp_store):
        r = tmp_store.add(name="Comp", source_type="file_md",
                          content_path="c.md", progress_path="pc.md", import_status=ImportStatus.ready)
        tmp_store.set_active(r.id)
        tmp_store.mark_completed(r.id)
        assert tmp_store.get(r.id).status == TextbookStatus.completed
        assert tmp_store.get_active_id() is None

    def test_import_status_transitions(self, tmp_store):
        r = tmp_store.add(name="Imp", source_type="url",
                          content_path="i.md", progress_path="pi.md",
                          import_status=ImportStatus.pending)
        assert r.import_status == ImportStatus.pending
        tmp_store.set_import_processing(r.id)
        assert tmp_store.get(r.id).import_status == ImportStatus.processing
        tmp_store.set_import_ready(r.id)
        assert tmp_store.get(r.id).import_status == ImportStatus.ready
        tmp_store.set_import_error(r.id, "bad")
        assert tmp_store.get(r.id).import_status == ImportStatus.failed
        assert tmp_store.get(r.id).import_error == "bad"
