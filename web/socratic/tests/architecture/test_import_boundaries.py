"""Architecture constraint: no cross-module impl.py imports except container."""
import ast
from pathlib import Path


ROOT = Path(__file__).parent.parent.parent.parent / "socratic"
ALLOWED_IMPL_IMPORTS = {"web/socratic/app/container.py"}


def _all_python_files():
    for f in ROOT.rglob("*.py"):
        yield f


def test_no_cross_module_impl_imports():
    violations = []
    for file in _all_python_files():
        if str(file).endswith("/container.py"):
            continue
        if not file.exists():
            continue
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.endswith(".impl") or ".impl." in node.module:
                    violations.append(f"{file} imports {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if ".impl" in alias.name:
                        violations.append(f"{file} imports {alias.name}")
    assert violations == [], "\n".join(violations)


def test_no_direct_fastapi_in_modules():
    violations = []
    for file in _all_python_files():
        if "adapters" in str(file) or "app" in str(file):
            continue
        if not file.exists():
            continue
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and ("fastapi" in node.module):
                    violations.append(f"{file} imports FastAPI ({node.module})")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "fastapi" in alias.name:
                        violations.append(f"{file} imports FastAPI ({alias.name})")
    assert violations == [], "\n".join(violations)


def test_no_anthropic_sdk_in_modules():
    violations = []
    for file in _all_python_files():
        if "infrastructure" in str(file) or "test" in str(file):
            continue
        if not file.exists():
            continue
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "anthropic" in node.module:
                    violations.append(f"{file} imports anthropic SDK ({node.module})")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if "anthropic" in alias.name:
                        violations.append(f"{file} imports anthropic SDK ({alias.name})")
    assert violations == [], "\n".join(violations)
