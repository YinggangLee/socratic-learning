import json
from datetime import datetime, timezone
from pathlib import Path

from textbook_models import TextbookRecord, TextbookStatus, ImportStatus


class TextbookStore:
    def __init__(self, registry_path: Path):
        self._registry_path = registry_path
        self._data: dict = {"textbooks": [], "active_textbook_id": None}
        if registry_path.exists():
            self._load()
        else:
            self._save()

    # ── CRUD ──

    def add(self, name: str, source_type: str, content_path: str,
            progress_path: str, source_ref: str = None,
            original_path: str = None,
            import_status: ImportStatus = ImportStatus.pending) -> TextbookRecord:
        from textbook_models import TextbookCreateRequest
        req = TextbookCreateRequest(name=name, source_type=source_type, source_ref=source_ref)
        tid = req._generate_id()
        existing_ids = {r["id"] for r in self._data["textbooks"]}
        base = tid
        counter = 2
        while tid in existing_ids:
            tid = f"{base}-{counter}"
            counter += 1
        record = TextbookRecord(
            id=tid, name=name, content_path=content_path,
            source_type=source_type, source_ref=source_ref,
            original_path=original_path, progress_path=progress_path,
            status=TextbookStatus.inactive, import_status=import_status,
        )
        self._data["textbooks"].append(record.model_dump())
        self._save()
        return record

    def get(self, textbook_id: str) -> TextbookRecord | None:
        for r in self._data["textbooks"]:
            if r["id"] == textbook_id:
                return TextbookRecord(**r)
        return None

    def list_all(self, show_deleted: bool = False) -> list[TextbookRecord]:
        result = [TextbookRecord(**r) for r in self._data["textbooks"]]
        if not show_deleted:
            result = [r for r in result if r.status != TextbookStatus.deleted]
        return result

    def set_active(self, textbook_id: str):
        record = self.get(textbook_id)
        if record is None:
            raise ValueError(f"textbook not found: {textbook_id}")
        if record.import_status != ImportStatus.ready:
            raise ValueError(f"cannot activate textbook with import_status={record.import_status.value}")
        self._update_status(textbook_id, TextbookStatus.active)
        if self._data["active_textbook_id"] and self._data["active_textbook_id"] != textbook_id:
            self._update_status(self._data["active_textbook_id"], TextbookStatus.inactive)
        self._data["active_textbook_id"] = textbook_id
        self._update_last_studied(textbook_id)
        self._save()

    def mark_completed(self, textbook_id: str):
        record = self.get(textbook_id)
        if record is None:
            raise ValueError(f"textbook not found: {textbook_id}")
        self._update_status(textbook_id, TextbookStatus.completed)
        if self._data["active_textbook_id"] == textbook_id:
            self._data["active_textbook_id"] = None
        self._save()

    def soft_delete(self, textbook_id: str):
        record = self.get(textbook_id)
        if record is None:
            raise ValueError(f"textbook not found: {textbook_id}")
        if record.status == TextbookStatus.active:
            raise ValueError("cannot delete active textbook")
        self._update_status(textbook_id, TextbookStatus.deleted)
        if self._data["active_textbook_id"] == textbook_id:
            self._data["active_textbook_id"] = None
        self._save()

    def restore(self, textbook_id: str):
        record = self.get(textbook_id)
        if record is None:
            raise ValueError(f"textbook not found: {textbook_id}")
        self._update_status(textbook_id, TextbookStatus.inactive)
        self._save()

    def set_import_error(self, textbook_id: str, error: str):
        self._update_field(textbook_id, "import_error", error)
        self._update_field(textbook_id, "import_status", ImportStatus.failed.value)
        self._save()

    def set_import_ready(self, textbook_id: str):
        self._update_field(textbook_id, "import_status", ImportStatus.ready.value)
        self._update_field(textbook_id, "import_error", None)
        self._save()

    def set_import_processing(self, textbook_id: str):
        self._update_field(textbook_id, "import_status", ImportStatus.processing.value)
        self._save()

    def get_active_paths(self) -> tuple[str | None, str | None]:
        aid = self._data.get("active_textbook_id")
        if not aid:
            return None, None
        record = self.get(aid)
        if record is None:
            return None, None
        return record.content_path, record.progress_path

    def get_active_id(self) -> str | None:
        return self._data.get("active_textbook_id")

    def has_active_textbook(self) -> bool:
        aid = self._data.get("active_textbook_id")
        if not aid:
            return False
        record = self.get(aid)
        return record is not None and record.import_status == ImportStatus.ready

    # ── Internal ──

    def _update_status(self, textbook_id: str, status: TextbookStatus):
        self._update_field(textbook_id, "status", status.value)

    def _update_last_studied(self, textbook_id: str):
        self._update_field(textbook_id, "last_studied_at",
                          datetime.now(timezone.utc).isoformat())

    def _update_field(self, textbook_id: str, field: str, value):
        for r in self._data["textbooks"]:
            if r["id"] == textbook_id:
                r[field] = value
                return

    def _load(self):
        text = self._registry_path.read_text(encoding="utf-8")
        self._data = json.loads(text)
        if "textbooks" not in self._data:
            self._data["textbooks"] = []
        if "active_textbook_id" not in self._data:
            self._data["active_textbook_id"] = None

    def _save(self):
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._registry_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._registry_path)
        self._render_registry_md()

    def _render_registry_md(self):
        md_path = self._registry_path.parent / "textbook_registry.md"
        lines = [
            "# 教材注册表",
            "",
            "> ⚠️ 此文件由 `registry.json` 自动生成，只读参考，请勿手动编辑。",
            "",
            "## 教材列表",
            "",
            "| 教材名称 | 路径 | 来源 | 状态 | 导入状态 |",
            "|----------|------|------|------|----------|",
        ]
        for r in self._data["textbooks"]:
            lines.append(
                f"| {r['name']} | {r['content_path']} | "
                f"{r['source_type']} | {r['status']} | {r['import_status']} |"
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


_store: TextbookStore | None = None


def get_store() -> TextbookStore:
    global _store
    if _store is None:
        from config import TEXTBOOK_DIR
        json_path = TEXTBOOK_DIR / "registry.json"
        if not json_path.exists():
            md_path = TEXTBOOK_DIR / "textbook_registry.md"
            if md_path.exists():
                from migrate_registry import migrate_from_legacy
                migrate_from_legacy(TEXTBOOK_DIR, json_path)
        _store = TextbookStore(json_path)
    return _store
