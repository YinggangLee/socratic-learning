"""Textbook catalog implementation — wraps TextbookStore."""

from datetime import UTC, datetime
from pathlib import Path

from .errors import InvalidTextbookStatus, TextbookNotFound
from .models import CreateTextbookCommand, ImportStatus, TextbookRecord, TextbookStatus


class JsonTextbookCatalog:
    def __init__(self, registry_path: Path, base_dir: Path):
        self._path = registry_path
        self._base_dir = base_dir
        self._data: dict = {"textbooks": [], "active_textbook_id": None}
        self._pending: set[str] = set()
        if registry_path.exists():
            self._load()
        else:
            self._save()

    # ── TextbookCatalog interface ──

    def list_textbooks(self, show_deleted: bool = False) -> list[TextbookRecord]:
        result = [TextbookRecord(**r) for r in self._data["textbooks"]]
        if not show_deleted:
            result = [r for r in result if r.status != TextbookStatus.deleted]
        return result

    def get_by_id(self, textbook_id: str) -> TextbookRecord | None:
        for r in self._data["textbooks"]:
            if r["id"] == textbook_id:
                return TextbookRecord(**r)
        return None

    def get_active(self) -> TextbookRecord | None:
        aid = self._data.get("active_textbook_id")
        if not aid:
            return None
        return self.get_by_id(aid)

    def create(self, command: CreateTextbookCommand) -> TextbookRecord:
        import re as _re

        raw = command.name.lower().strip()
        raw = _re.sub(r"[^a-z0-9\s-]", "", raw)
        raw = _re.sub(r"\s+", "-", raw)
        base_id = raw.strip("-") or "untitled"

        existing_ids = {r["id"] for r in self._data["textbooks"]}
        tid = base_id
        counter = 2
        while tid in existing_ids:
            tid = f"{base_id}-{counter}"
            counter += 1

        record = TextbookRecord(
            id=tid,
            name=command.name,
            content_path="__pending__",
            progress_path="__pending__",
            source_type=command.source_type,
            source_ref=command.source_ref,
            status=TextbookStatus.inactive,
            import_status=ImportStatus.pending,
        )
        self._data["textbooks"].append(record.__dict__)
        self._save()
        return record

    def activate(self, textbook_id: str) -> TextbookRecord:
        record = self.get_by_id(textbook_id)
        if record is None:
            raise TextbookNotFound(textbook_id)
        if record.import_status != ImportStatus.ready:
            raise InvalidTextbookStatus(record.status.value, "active", "import not ready")
        self._update_status(textbook_id, TextbookStatus.active)
        if self._data["active_textbook_id"] and self._data["active_textbook_id"] != textbook_id:
            self._update_status(self._data["active_textbook_id"], TextbookStatus.inactive)
        self._data["active_textbook_id"] = textbook_id
        self._update_last_studied(textbook_id)
        self._save()
        return self.get_by_id(textbook_id)  # type: ignore[return-value]

    def mark_completed(self, textbook_id: str) -> TextbookRecord:
        record = self.get_by_id(textbook_id)
        if record is None:
            raise TextbookNotFound(textbook_id)
        self._update_status(textbook_id, TextbookStatus.completed)
        if self._data["active_textbook_id"] == textbook_id:
            self._data["active_textbook_id"] = None
        self._save()
        return self.get_by_id(textbook_id)  # type: ignore[return-value]

    def soft_delete(self, textbook_id: str) -> TextbookRecord:
        record = self.get_by_id(textbook_id)
        if record is None:
            raise TextbookNotFound(textbook_id)
        if record.status == TextbookStatus.active:
            raise InvalidTextbookStatus(record.status.value, "deleted", "cannot delete active textbook")
        self._update_status(textbook_id, TextbookStatus.deleted)
        if self._data["active_textbook_id"] == textbook_id:
            self._data["active_textbook_id"] = None
        self._save()
        return self.get_by_id(textbook_id)  # type: ignore[return-value]

    def restore(self, textbook_id: str) -> TextbookRecord:
        record = self.get_by_id(textbook_id)
        if record is None:
            raise TextbookNotFound(textbook_id)
        self._update_status(textbook_id, TextbookStatus.inactive)
        self._save()
        return self.get_by_id(textbook_id)  # type: ignore[return-value]

    # ── Extended operations needed by other modules ──

    def get_active_id(self) -> str | None:
        return self._data.get("active_textbook_id")

    def get_active_paths(self) -> tuple[str | None, str | None]:
        aid = self._data.get("active_textbook_id")
        if not aid:
            return None, None
        record = self.get_by_id(aid)
        if record is None:
            return None, None
        return record.content_path, record.progress_path

    def has_active_textbook(self) -> bool:
        aid = self._data.get("active_textbook_id")
        if not aid:
            return False
        record = self.get_by_id(aid)
        return record is not None and record.import_status == ImportStatus.ready

    def _update_field(self, textbook_id: str, field: str, value):
        for r in self._data["textbooks"]:
            if r["id"] == textbook_id:
                r[field] = value
                return

    def update_content_path(self, textbook_id: str, content_path: str):
        self._update_field(textbook_id, "content_path", content_path)
        self._save()

    def update_progress_path(self, textbook_id: str, progress_path: str):
        self._update_field(textbook_id, "progress_path", progress_path)
        self._save()

    def update_source_ref(self, textbook_id: str, source_ref: str):
        self._update_field(textbook_id, "source_ref", source_ref)
        self._save()

    def update_original_path(self, textbook_id: str, original_path: str):
        self._update_field(textbook_id, "original_path", original_path)
        self._save()

    def set_import_error(self, textbook_id: str, error: str):
        self._update_field(textbook_id, "import_error", error)
        self._update_field(textbook_id, "import_status", ImportStatus.failed.value)
        self._save()

    def set_import_ready(self, textbook_id: str):
        self._update_field(textbook_id, "import_status", ImportStatus.ready.value)
        self._update_field(textbook_id, "import_error", None)
        self._save()
        if textbook_id in self._pending:
            self._pending.discard(textbook_id)
            self.activate(textbook_id)

    def set_import_processing(self, textbook_id: str):
        self._update_field(textbook_id, "import_status", ImportStatus.processing.value)
        self._save()

    def mark_pending_activation(self, textbook_id: str):
        self._pending.add(textbook_id)

    # ── Internal ──

    def _update_status(self, textbook_id: str, status: TextbookStatus):
        self._update_field(textbook_id, "status", status.value)

    def _update_last_studied(self, textbook_id: str):
        self._update_field(textbook_id, "last_studied_at", datetime.now(UTC).isoformat())

    def _load(self):
        import json

        text = self._path.read_text(encoding="utf-8")
        try:
            self._data = json.loads(text)
        except json.JSONDecodeError:
            self._data = {"textbooks": [], "active_textbook_id": None}
            return

    def _save(self):
        import json

        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)
        self._render_md()

    def _render_md(self):
        md_path = self._path.parent / "textbook_registry.md"
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
                f"| {r['name']} | {r['content_path']} | {r['source_type']} | {r['status']} | {r['import_status']} |"
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
