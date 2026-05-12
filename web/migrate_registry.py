import re, json
from pathlib import Path
from datetime import datetime, timezone


def _slugify(text: str) -> str:
    raw = text.lower().strip()
    # Strip file extension
    if raw.endswith(".md"):
        raw = raw[:-3]
    raw = re.sub(r'[^a-z0-9\s-]', '', raw)
    raw = re.sub(r'\s+', '-', raw)
    return raw.strip('-') or "untitled"


def migrate_from_legacy(textbook_dir: Path, json_path: Path):
    """Migrate old textbook_registry.md → registry.json. Idempotent."""
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
        status_str = parts[3].lower() if len(parts) > 3 else "inactive"
        source_str = parts[2] if len(parts) > 2 else ""
        tid = _slugify(path_str.rstrip("/").split("/")[-1])
        resolved = (textbook_dir / "..").resolve() / path_str
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
