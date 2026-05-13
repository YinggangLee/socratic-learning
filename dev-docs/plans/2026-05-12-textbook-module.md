# 教材模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增教材管理模块——`registry.json` 唯一数据源，支持 Markdown/PDF/URL 导入，选择 active 教材，软删除/恢复，前端全生命周期管理。

**Architecture:** 新增 `textbook_store.py` 负责 JSON 读写和状态流转，`textbook_importer.py` 负责三种来源的导入。改造 `config.py` 的 `get_active_textbook()` 从 store 查 active record。全教学链路（prompt、panel、课后）改为使用 record 的显式路径。前端新增教材面板，走 JSON API 渲染。

**Tech Stack:** FastAPI + Pydantic + PyMuPDF + BeautifulSoup4 + python-multipart + 现有 Anthropic-compatible client

**保存位置:** `dev-docs/plans/2026-05-12-textbook-module.md`

---

### Task 1: 依赖补全

**Files:**
- Modify: `web/requirements.txt`
- Modify: `web/requirements-dev.txt`

- [ ] **Step 1: 补全生产依赖**

编辑 `web/requirements.txt`：
```txt
anthropic>=0.50.0
tiktoken
python-dotenv
fastapi>=0.115.0
uvicorn>=0.30.0
pydantic>=2.0.0
python-multipart>=0.0.9
httpx>=0.27.0
beautifulsoup4>=4.12.0
PyMuPDF>=1.24.0
```

- [ ] **Step 2: 补全开发依赖**

编辑 `web/requirements-dev.txt`：
```txt
-r requirements.txt
pytest>=7.0.0
pytest-asyncio>=0.24.0
httpx>=0.27.0
```

- [ ] **Step 3: 安装依赖**

```bash
pip install -r web/requirements-dev.txt
```

- [ ] **Step 4: 编译验证**

```bash
python3 -m py_compile web/*.py && echo "OK"
```

- [ ] **Step 5: Commit**

```bash
git add web/requirements.txt web/requirements-dev.txt
git commit -m "chore: add textbook module dependencies"
```

---

### Task 2: TextbookRecord 等 Pydantic 模型

**Files:**
- Create: `web/textbook_models.py`
- Test: `web/tests/test_textbook_models.py`

- [ ] **Step 1: 写失败的模型测试**

创建 `web/tests/test_textbook_models.py`：
```python
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

    def test_invalid_source_type_raises(self):
        with pytest.raises(ValueError):
            TextbookRecord(
                id="x", name="X", content_path="x.md",
                source_type="invalid", progress_path="p.md",
                status="active", import_status="ready",
            )

    def test_active_requires_ready_import(self):
        with pytest.raises(ValueError):
            TextbookRecord(
                id="x", name="X", content_path="x.md",
                source_type="url", progress_path="p.md",
                status="active", import_status="pending",
            )


class TestTextbookCreateRequest:
    def test_minimal_fields(self):
        r = TextbookCreateRequest(name="New Book", source_type="url", source_ref="https://example.com")
        assert r.name == "New Book"

    def test_pdf_requires_file(self):
        with pytest.raises(ValueError):
            TextbookCreateRequest(name="PDF Book", source_type="file_pdf", source_ref="")

    def test_auto_generates_id(self):
        r = TextbookCreateRequest(name="Building Effective Agents!", source_type="url", source_ref="https://x.com")
        assert r._generate_id() == "building-effective-agents"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python3 -m pytest web/tests/test_textbook_models.py -v
```
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 实现模型**

创建 `web/textbook_models.py`：
```python
import re
from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, Field, model_validator


class TextbookStatus(StrEnum):
    active = "active"
    inactive = "inactive"
    completed = "completed"
    deleted = "deleted"


class ImportStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class TextbookRecord(BaseModel):
    id: str
    name: str
    content_path: str
    source_type: str  # file_md / file_pdf / url
    source_ref: str | None = None
    original_path: str | None = None
    progress_path: str
    status: TextbookStatus = TextbookStatus.inactive
    import_status: ImportStatus = ImportStatus.pending
    import_error: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_studied_at: str | None = None

    @model_validator(mode="after")
    def active_requires_ready(self):
        if self.status == TextbookStatus.active and self.import_status != ImportStatus.ready:
            raise ValueError("active status requires import_status=ready")
        return self


class TextbookCreateRequest(BaseModel):
    name: str
    source_type: str  # file_md / file_pdf / url
    source_ref: str | None = None
    set_active: bool = False

    def _generate_id(self) -> str:
        raw = self.name.lower().strip()
        raw = re.sub(r'[^a-z0-9\s-]', '', raw)
        raw = re.sub(r'\s+', '-', raw)
        return raw.strip('-') or "untitled"


class TextbookStatusRequest(BaseModel):
    status: TextbookStatus
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m pytest web/tests/test_textbook_models.py -v
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add web/textbook_models.py web/tests/test_textbook_models.py
git commit -m "feat: add TextbookRecord and related Pydantic models"
```

---

### Task 3: textbook_store.py — JSON 读写和状态流转

**Files:**
- Create: `web/textbook_store.py`
- Test: `web/tests/test_textbook_store.py`

- [ ] **Step 1: 写失败的 store 测试**

创建 `web/tests/test_textbook_store.py`：
```python
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
        # Now activate B, A becomes inactive
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

    def test_get_active_textbook(self, tmp_store):
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

    def test_atomic_write_preserves_data(self, tmp_store):
        r = tmp_store.add(name="Persist", source_type="file_md",
                          content_path="p.md", progress_path="pp.md", import_status=ImportStatus.ready)
        # Reload from disk
        store2 = TextbookStore(registry_path=tmp_store._registry_path)
        assert store2.get(r.id) is not None
        assert store2.get(r.id).name == "Persist"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python3 -m pytest web/tests/test_textbook_store.py -v
```

- [ ] **Step 3: 实现 textbook_store.py**

```python
import json
import shutil
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
        # Resolve ID conflicts
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
            raise ValueError(f"cannot activate textbook with import_status={record.import_status}")
        self._update_status(textbook_id, TextbookStatus.active)
        # Deactivate current active
        if self._data["active_textbook_id"] and self._data["active_textbook_id"] != textbook_id:
            self._update_status(self._data["active_textbook_id"], TextbookStatus.inactive)
        self._data["active_textbook_id"] = textbook_id
        self._update_last_studied(textbook_id)
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
        """Return (content_path, progress_path) for the active textbook."""
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

    def _save(self):
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._registry_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._registry_path)
        self._render_registry_md()

    def _render_registry_md(self):
        """Generate human-readable textbook_registry.md from JSON."""
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


# Module-level singleton
_store: TextbookStore | None = None


def get_store() -> TextbookStore:
    global _store
    if _store is None:
        from config import TEXTBOOK_DIR
        _store = TextbookStore(TEXTBOOK_DIR / "registry.json")
    return _store
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m pytest web/tests/test_textbook_store.py -v
```

- [ ] **Step 5: Commit**

```bash
git add web/textbook_store.py web/tests/test_textbook_store.py
git commit -m "feat: add TextbookStore — JSON registry CRUD with atomic writes"
```

---

### Task 4: 替换 get_active_textbook() 为 store 查询

**Files:**
- Modify: `web/config.py` — 替换 `get_active_textbook()` 为委托给 store
- Modify: `web/prompt_builder.py` — 适配新返回签名
- Modify: `web/panels.py` — 适配新返回签名
- Modify: `web/server.py` — 适配新返回签名

- [ ] **Step 1: 修改 config.py**

替换 `get_active_textbook()` 为委托给 store 的版本：

```python
def get_active_textbook() -> tuple[Path | None, str | None]:
    """Return (content_path, progress_path) from active textbook in registry.
    Falls back to building-effective-agents.md for legacy compatibility."""
    from textbook_store import get_store
    store = get_store()
    content, progress = store.get_active_paths()
    if content and progress:
        return BASE_DIR / content, BASE_DIR / progress
    # Legacy fallback
    default = TEXTBOOK_DIR / "building-effective-agents.md"
    if default.exists():
        return default, None
    return None, None
```

- [ ] **Step 2: 修改 prompt_builder.py 适配新签名**

`get_active_textbook()` 当前返回 `tuple[Path, str]`（content_path, progress_stem）。改成 `tuple[Path | None, str | None]`（content_path, progress_path），其中 `progress_path` 改为完整路径。

更新 `_get_active_progress()`：
```python
def _get_active_progress() -> tuple[Path | None, str]:
    _, progress_path = get_active_textbook()
    if progress_path and progress_path.exists():
        return progress_path, progress_path.stem.replace("-", " ").title()
    progress_dir = TEACHER_DIR / "progress"
    if not progress_dir.exists():
        return None, ""
    for f in sorted(progress_dir.iterdir()):
        if f.suffix == ".md":
            return f, f.stem.replace("-", " ").title()
    return None, ""
```

并更新所有 `get_active_textbook()` 调用，解包为 `(content, _)`：
```python
textbook_content_path, _ = get_active_textbook()
textbook = _read(textbook_content_path) if textbook_content_path else ""
```

- [ ] **Step 3: 修改 panels.py 适配新签名**

`render_progress()` 改为直接用 `_get_active_progress()`：
```python
def render_progress() -> str:
    from prompt_builder import _get_active_progress
    progress_file, _ = _get_active_progress()
    if progress_file and progress_file.exists():
        return _md_to_html(_read(progress_file))
    return "<p>暂无进度记录</p>"
```

`render_toc()` 适配：
```python
def render_toc() -> str:
    from config import get_active_textbook
    textbook_path, _ = get_active_textbook()
    if textbook_path is None:
        return "<p>教材未找到</p>"
    text = _read(textbook_path)
    ...
```

- [ ] **Step 4: 修改 server.py 适配**

`_run_post_lesson` 中的 `_get_active_progress()` 保持正常（它已从 prompt_builder 导入）；删除冗余的 `from config import TEACHER_DIR`。

- [ ] **Step 5: 编译和测试验证**

```bash
python3 -m py_compile web/config.py web/prompt_builder.py web/panels.py web/server.py
python3 -m pytest web/tests/ -v
```

- [ ] **Step 6: Commit**

```bash
git add web/config.py web/prompt_builder.py web/panels.py web/server.py
git commit -m "refactor: replace get_active_textbook() with store-based lookup"
```

---

### Task 5: 迁移脚本

**Files:**
- Create: `web/migrate_registry.py` — 一次性迁移脚本
- Test: `web/tests/test_migrate_registry.py`

- [ ] **Step 1: 写迁移测试**

```python
# web/tests/test_migrate_registry.py
import sys, json, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from migrate_registry import migrate_from_legacy


def test_migrate_single_md_textbook(tmp_path):
    textbook_dir = tmp_path / "textbook"
    textbook_dir.mkdir()
    legacy_registry = textbook_dir / "textbook_registry.md"
    legacy_registry.write_text(
        "| 教材名称 | 路径 | 来源 | 状态 |\n"
        "|----------|------|------|------|\n"
        "| Building Effective Agents | textbook/building-effective-agents.md | "
        "URL: https://www.anthropic.com/engineering/building-effective-agents | active |\n"
    )
    # Create the actual textbook file
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
    assert data["textbooks"][0]["progress_path"] == "teacher/progress/google-ai-agent-whitepapers.md"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
python3 -m pytest web/tests/test_migrate_registry.py -v
```

- [ ] **Step 3: 实现迁移脚本**

```python
# web/migrate_registry.py
import re, json
from pathlib import Path
from datetime import datetime, timezone


def _slugify(text: str) -> str:
    raw = text.lower().strip()
    raw = re.sub(r'[^a-z0-9\s-]', '', raw)
    raw = re.sub(r'\s+', '-', raw)
    return raw.strip('-') or "untitled"


def migrate_from_legacy(textbook_dir: Path, json_path: Path):
    registry_md = textbook_dir / "textbook_registry.md"
    if not registry_md.exists():
        return
    lines = registry_md.read_text(encoding="utf-8").split("\n")
    textbooks = []
    active_id = None
    now = datetime.now(timezone.utc).isoformat()
    for line in lines:
        if not line.startswith("|") or "---|---" in line or "教材名称" in line:
            continue
        parts = [c.strip() for c in line.split("|")]
        parts = [p for p in parts if p]
        if len(parts) < 3:
            continue
        name = parts[0]
        path_str = parts[1]
        source_str = parts[2] if len(parts) > 2 else ""
        status_str = parts[3].lower() if len(parts) > 3 else "inactive"
        tid = _slugify(name.split("/")[-1] if "/" in name else name)
        resolved = textbook_dir.parent / path_str
        content_path = path_str
        if resolved.is_dir():
            for f in sorted(resolved.iterdir()):
                if f.suffix == ".md":
                    content_path = str(Path(path_str) / f.name)
                    break
        source_type = "url" if "http" in source_str else "file_md"
        source_ref = source_str.replace("URL: ", "").strip() if "URL:" in source_str else None
        record = {
            "id": tid,
            "name": name,
            "content_path": content_path,
            "source_type": source_type,
            "source_ref": source_ref,
            "original_path": None,
            "progress_path": f"teacher/progress/{tid}.md",
            "status": "inactive",
            "import_status": "ready",
            "import_error": None,
            "created_at": now,
            "last_studied_at": None,
        }
        textbooks.append(record)
        if "active" in status_str and "inactive" not in status_str:
            record["status"] = "active"
            active_id = tid
    data = {"textbooks": textbooks, "active_textbook_id": active_id}
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: 运行测试确认通过**

```bash
python3 -m pytest web/tests/test_migrate_registry.py -v
```

- [ ] **Step 5: 在 TextbookStore 初始化时调用迁移**

在 `get_store()` 中：首次访问时，如果 `registry.json` 不存在但 `textbook_registry.md` 存在，调用 `migrate_from_legacy()`。

```python
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
```

- [ ] **Step 6: Commit**

```bash
git add web/migrate_registry.py web/tests/test_migrate_registry.py web/textbook_store.py
git commit -m "feat: add migration from legacy textbook_registry.md to registry.json"
```

---

### Task 6: textbook_importer.py — Markdown/PDF/URL 导入

**Files:**
- Create: `web/textbook_importer.py`
- Test: `web/tests/test_textbook_importer.py`

- [ ] **Step 1: 写导入器测试**

```python
# web/tests/test_textbook_importer.py
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from textbook_importer import (
    import_markdown_file, create_textbook_dirs, slugify_name,
)


class TestSlugifyName:
    def test_basic(self):
        assert slugify_name("Building Effective Agents") == "building-effective-agents"
    def test_special_chars(self):
        assert slugify_name("Hello! World?") == "hello-world"


class TestCreateDirs:
    def test_creates_paths(self, tmp_path):
        content, progress = create_textbook_dirs(
            name="Test Book", base_dir=tmp_path)
        assert content.parent.exists()
        assert progress.parent.exists()


class TestImportMarkdown:
    def test_import_md_file(self, tmp_path):
        # Create a temp .md file
        src = tmp_path / "source.md"
        src.write_text("# Hello\n\nWorld")
        content, progress = create_textbook_dirs("My Book", tmp_path)
        result = import_markdown_file(src, content)
        assert result is True
        assert content.read_text() == "# Hello\n\nWorld"

    def test_import_empty_file_fails(self, tmp_path):
        src = tmp_path / "empty.md"
        src.write_text("")
        content = tmp_path / "content.md"
        result = import_markdown_file(src, content)
        assert result is False
```

- [ ] **Step 2: 运行测试确认失败** → **Step 3: 实现导入器** → **Step 4: 测试通过** → **Step 5: Commit**

---

### Task 7: API 路由 — /api/textbooks/*

**Files:**
- Modify: `web/server.py` — 新增教材路由
- Create: `web/tests/test_textbook_api.py`

**核心 endpoints：** GET `/api/textbooks`, POST `/api/textbooks`, GET `/{id}`, PUT `/{id}/status`, POST `/{id}/restore`, POST `/{id}/retry-import`, GET `/registry.md`

- [ ] 逐步实现每个 endpoint（先写测试，再实现）

---

### Task 8: 前端教材面板

**Files:**
- Modify: `web/static/index.html` — 新增教材面板、新增教材弹窗、上课中锁定

**核心变更：**
- 菜单新增"教材 📚"tab
- `loadPanel('textbooks')` 走 JSON API 渲染（不走 Markdown panel HTML）
- 教材卡片列表 + 新增教材弹窗
- 上课中按钮置灰
- 无 active 教材时开始按钮禁用 + 引导文案

---

### Task 9: 集成测试与端到端验证

- 迁移现有数据验证
- 教材导入全过程测试
- 教学链路一致性验证
- 切换教材后进度独立性验证
