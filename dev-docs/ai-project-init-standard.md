# Python 项目 AI 初始化规范

> 给 AI 用的精简版。新项目时把这份文档丢给 AI，让它按此标准初始化。

---

## 1. 技术选型（固定）

| 维度 | 工具 | 锁定原因 |
|------|------|----------|
| 包管理 | `uv` | 快、PEP 621、锁文件可靠 |
| 配置入口 | `pyproject.toml` | 唯一入口，不用 requirements.txt |
| 命令入口 | `Makefile` | 本地和 CI 命令统一 |
| 格式化 | `ruff format` | 快、零配置争议 |
| Lint | `ruff check` | 同工具、规则齐全 |
| 类型检查 | `mypy` | 渐进可配 |
| 测试 | `pytest` + `pytest-asyncio` | 标准选型 |
| 提交检查 | `pre-commit` | 强制门禁 |

---

## 2. 项目结构

```
<project>/
  pyproject.toml
  Makefile
  .pre-commit-config.yaml
  .python-version          # 内容: 3.12
  .env.example
  .gitignore
  src/
    <project>/
      __init__.py
      app/
        __init__.py
        config.py           # pydantic-settings
        container.py        # Composition Root
      modules/
        __init__.py
      infrastructure/
        __init__.py
      adapters/
        __init__.py
        api.py              # FastAPI app factory
  tests/
    __init__.py
    conftest.py
```

如果是应用（非库），`src/` 可换为项目名直接放根下。

---

## 3. AI 初始化执行清单

收到初始化指令后，AI 应按以下顺序创建文件：

### 3a. `.python-version`
```
3.12
```

### 3b. `pyproject.toml`

```toml
[project]
name = "<project-name>"
version = "0.1.0"
description = "<一句话描述>"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = [
    "coverage[toml]>=7.6.0",
    "mypy>=1.14.0",
    "pre-commit>=4.0.0",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.11.0",
]

[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]
exclude = [".git", ".venv", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101"]

[tool.mypy]
python_version = "3.12"
ignore_missing_imports = true
check_untyped_defs = true
warn_return_any = true
disallow_untyped_defs = false
files = ["src", "tests"]

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = ["-ra", "--strict-markers"]
markers = [
    "unit: 快速单元测试",
    "integration: 需要外部依赖",
    "slow: 慢速测试",
]
```

### 3c. `Makefile`

```makefile
.DEFAULT_GOAL := help
export PATH := $(HOME)/.local/bin:$(PATH)
UV ?= $(HOME)/.local/bin/uv
APP_MODULE ?= <project>.adapters.api:create_app
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: help install sync dev run test test-unit format format-check lint lint-fix typecheck check clean venv

help:
	@echo "make install      一键环境搭建"
	@echo "make dev          开发启动 (reload)"
	@echo "make test         全部测试"
	@echo "make check        完整质量门禁"

ensure-uv:
	@command -v $(UV) >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
	@$(UV) --version >/dev/null

ensure-python:
	@$(UV) python install --no-prompt 2>/dev/null || true

install: ensure-python ensure-uv
	$(UV) sync --group dev
	$(UV) run pre-commit install 2>/dev/null || true
	@echo "✓ 环境就绪"

sync: ensure-uv
	$(UV) sync --group dev

dev: ensure-uv
	$(UV) run uvicorn $(APP_MODULE) --factory --host $(HOST) --port $(PORT) --reload

run: ensure-uv
	$(UV) run uvicorn $(APP_MODULE) --factory --host $(HOST) --port $(PORT)

test: ensure-uv
	$(UV) run pytest

test-unit: ensure-uv
	$(UV) run pytest -m "not slow and not integration"

format: ensure-uv
	$(UV) run ruff format src tests
	$(UV) run ruff check --fix src tests

format-check: ensure-uv
	$(UV) run ruff format --check src tests

lint: ensure-uv
	$(UV) run ruff check src tests

lint-fix: ensure-uv
	$(UV) run ruff check --fix src tests

typecheck: ensure-uv
	$(UV) run mypy

check: format-check lint typecheck test
	@echo "✓ 全部检查通过"

venv: ensure-uv
	rm -rf .venv
	$(UV) sync --group dev

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .pytest_cache .ruff_cache .coverage htmlcov
```

### 3d. `.pre-commit-config.yaml`

```yaml
repos:
  - repo: local
    hooks:
      - id: format-check
        name: ruff format --check
        entry: uv run ruff format --check src tests
        language: system
        pass_filenames: false
      - id: lint
        name: ruff check
        entry: uv run ruff check src tests
        language: system
        pass_filenames: false
      - id: typecheck
        name: mypy
        entry: uv run mypy
        language: system
        pass_filenames: false
```

### 3e. `.env.example`

```bash
APP_ENV=local
HOST=127.0.0.1
PORT=8000
LOG_LEVEL=INFO
```

### 3f. `.gitignore`

```gitignore
.env
.venv/
.mypy_cache/
.pytest_cache/
.ruff_cache/
__pycache__/
*.pyc
uv.lock
```

### 3g. `src/<project>/app/config.py`

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    app_env: str = "local"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
```

### 3h. `src/<project>/adapters/api.py`

```python
from fastapi import FastAPI

from ..app.config import Settings
from ..app.container import AppContainer


def create_app() -> FastAPI:
    settings = Settings()
    container = AppContainer(settings)

    app = FastAPI(title="<project-name>")
    app.state.settings = settings
    app.state.container = container

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
```

### 3i. `src/<project>/app/container.py`

```python
from dataclasses import dataclass

from .config import Settings


@dataclass
class AppContainer:
    settings: Settings
```

### 3j. `tests/conftest.py`

```python
import pytest

from <project>.app.config import Settings
from <project>.app.container import AppContainer


@pytest.fixture
def settings():
    return Settings(app_env="test")


@pytest.fixture
def container(settings):
    return AppContainer(settings=settings)
```

---

## 4. AI 初始化执行步骤

收到 `<project-name>` 和 `<描述>` 后：

```
1. 创建目录结构（src/<project>/app/, modules/, infrastructure/, adapters/, tests/）
2. 按 3a-3j 写入所有文件，替换 <project-name> 和 <描述> 占位符
3. 执行: uv sync --group dev
4. 执行: make format
5. 执行: make check
6. 报告结果
```

如果项目需要额外运行时依赖（如 fastapi），在步骤 2 后执行 `uv add <package>` 再继续。

---

## 5. 架构硬约束（AI 写代码时必须遵守）

1. **依赖方向**：`adapters → modules/interface`、`application → modules/interface`。不能反向。
2. **实现隔离**：只有 `app/container.py` 可以 `import ...impl`。
3. **模块自治**：每个业务模块必须有 `interface.py`（对外契约）和 `impl.py`（默认实现）。
4. **业务纯粹**：`modules/` 下的代码不能 import `fastapi`、`sqlalchemy`、`httpx`、`boto3` 等外部技术。
5. **副作用抽象**：文件读写、网络请求、时间、UUID 都通过接口注入，不在业务代码里直接调用。
6. **API 薄层**：route handler 只做三件事——解析请求、调用 service、返回响应。不写业务逻辑。

---

## 6. 测试规范

```text
tests/
  unit/             # 纯逻辑，不用 mock 外部服务
  contract/         # 接口契约，验证不同实现遵循同一接口
  integration/      # 真实文件系统、测试数据库
  architecture/     # import 边界、分层规则（AST 扫描）
```

必须有的架构测试：

```python
# tests/architecture/test_imports.py
import ast
from pathlib import Path


def test_only_container_imports_module_impl():
    root = Path("src/<project>")
    allowed = {root / "app" / "container.py"}

    for file in root.rglob("*.py"):
        if file in allowed:
            continue
        tree = ast.parse(file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.endswith(".impl"), \
                    f"{file} imports {node.module}"


def test_modules_dont_import_web_frameworks():
    root = Path("src/<project>/modules")
    for file in root.rglob("*.py"):
        tree = ast.parse(file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "fastapi" not in node.module, \
                    f"{file} imports fastapi"
```

---

## 7. 错误处理底线

AI 生成的代码必须遵守：

- `except` 必须捕获具体异常类型，或至少 `(JsonDecodeError, KeyError, TypeError)` 三个一组
- JSON/文件解析必须有降级路径，不能裸 `json.loads()` 无 try
- 流式输出（SSE/WebSocket）必须检测客户端断开
- 后台任务必须持有返回值的引用，防止被 GC
- CORS 不能 `allow_origins=["*"]` + `allow_credentials=True` 同时出现

---

## 8. 初始化完成验收

```bash
make install     # ✓ 一键安装
make check       # ✓ format + lint + typecheck + test 全通过
make dev         # ✓ 服务启动，/health 返回 200
```
