"""File system storage implementation."""

from pathlib import Path


class LocalFileStorage:
    def read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.rename(path)

    def exists(self, path: Path) -> bool:
        return path.exists()

    def ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)


class LocalJsonStore:
    def __init__(self, filepath: Path):
        self._path = filepath

    def load(self) -> dict:
        import json

        if self._path.exists():
            return json.loads(self._path.read_text(encoding="utf-8"))
        return {}

    def save(self, data: dict) -> None:
        import json

        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)
