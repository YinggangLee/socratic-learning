# Python 项目架构与工程化治理规范

> 适用范围：FastAPI / CLI / 后台任务 / 本地工具型 Python 项目。  
> 推荐栈：`uv + pyproject.toml + Makefile + Ruff + Mypy + Pytest + pre-commit`。  
> 核心目标：模块自治、接口驱动、依赖注入、统一启动、统一检查、可测试、可渐进迁移。

---

## 1. 总体原则

### 1.1 架构原则

1. 业务能力按 feature/module 拆分，不按“大工具文件”堆放。
2. 每个业务模块必须显式定义稳定接口。
3. 跨模块调用只能依赖接口，不能依赖实现类。
4. 实现类只能在 Composition Root / DI Container / Factory 中实例化。
5. 业务模块不得直接依赖 FastAPI、数据库 SDK、LLM SDK、HTTP SDK、文件系统等外部技术实现。
6. 所有副作用必须通过接口抽象，包括文件读写、数据库、网络、LLM、时间、UUID、后台任务。
7. API / CLI / WebSocket / UI 只做入口适配，不承载核心业务逻辑。
8. Application Service 负责编排业务流程，Domain Module 负责业务能力，Infrastructure 负责技术实现。
9. 支持渐进式迁移，不要求一次性重写旧系统。
10. 新功能必须先定义接口、DTO、错误类型，再实现默认实现。

### 1.2 工程化原则

1. `pyproject.toml` 是 Python 项目的唯一依赖与工具配置入口。
2. 不再使用 `requirements.txt` / `requirements-dev.txt` 作为最终依赖管理方式。
3. 使用 `uv` 管理依赖、锁文件和命令运行。
4. `Makefile` 是唯一开发命令入口。
5. 本地命令与 CI 命令保持一致。
6. 使用 `ruff format` 统一格式化。
7. 使用 `ruff check` 做 lint 和 import sorting。
8. 使用 `mypy` 做静态类型检查，允许渐进收紧。
9. 使用 `pytest` 做测试，测试按 unit / integration / contract / architecture 分层。
10. 使用 `pre-commit` 在提交前运行快速质量门禁。

---

## 2. 推荐目录结构

```text
project-root/
  pyproject.toml
  uv.lock
  Makefile
  .python-version
  .env.example
  .pre-commit-config.yaml
  README.md

  src/
    project_name/
      __init__.py

      app/
        __init__.py
        config.py
        container.py
        lifecycle.py

      application/
        __init__.py
        lesson_service.py
        textbook_service.py
        panel_service.py

      modules/
        lesson/
          __init__.py
          interface.py
          impl.py
          models.py
          errors.py
        textbook/
          __init__.py
          interface.py
          impl.py
          models.py
          errors.py
        prompt/
          __init__.py
          interface.py
          impl.py
          models.py
          errors.py

      infrastructure/
        llm/
          __init__.py
          interface.py
          anthropic_impl.py
          fake_impl.py
        storage/
          __init__.py
          interface.py
          filesystem_impl.py
          json_repository_impl.py
        http/
          __init__.py
          httpx_impl.py
        jobs/
          __init__.py
          asyncio_impl.py

      adapters/
        api/
          __init__.py
          app.py
          dependencies.py
          routes.py
          schemas.py
        cli/
          __init__.py
          main.py

  tests/
    unit/
    application/
    contract/
    integration/
    architecture/

  scripts/
    check_architecture.py

  .github/
    workflows/
      ci.yml
```

如果是历史项目，允许先保留旧目录，例如 `web/`，但新代码应逐步迁入类似结构：

```text
web/
  server.py                  # 兼容入口，最终变薄
  project_name/
    app/
    application/
    modules/
    infrastructure/
    adapters/
```

---

## 3. 分层职责

| 层级 | 职责 | 禁止事项 |
|---|---|---|
| `adapters/` | FastAPI、CLI、WebSocket、UI 入口适配；请求解析；响应映射 | 写业务逻辑；直接访问 DB/文件/LLM SDK |
| `application/` | 编排用例流程；事务/任务/跨模块协调；错误转换 | 依赖具体实现类；直接 new SDK client |
| `modules/` | 业务能力模块；领域模型；接口；默认业务实现 | 依赖 FastAPI、HTTP SDK、数据库 SDK、LLM SDK |
| `infrastructure/` | 文件系统、数据库、LLM、HTTP、缓存、日志、任务队列等技术实现 | 承载业务规则 |
| `app/` | 配置、DI 容器、生命周期、Composition Root | 写具体业务流程 |
| `tests/` | 单元、契约、集成、架构规则测试 | 依赖真实生产环境状态 |

---

## 4. 模块规范

每个业务模块必须包含：

```text
modules/<feature>/
  interface.py    # Protocol / ABC / DTO / Command / Query / Result
  impl.py         # 默认实现，仅 container 可直接实例化
  models.py       # 领域模型、值对象、内部数据结构
  errors.py       # 模块专属异常
  __init__.py     # 只暴露稳定接口和模型，不暴露实现类
```

### 4.1 `interface.py`

必须定义：

- 对外协议：`XxxService`、`XxxRepository`、`XxxGateway`、`XxxRenderer`
- 输入 DTO：`XxxCommand`、`XxxQuery`
- 输出 DTO：`XxxResult`、`XxxView`
- 必要的枚举和值对象

示例：

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StartLessonCommand:
    student_id: str | None = None


@dataclass(frozen=True)
class StartLessonResult:
    teacher_name: str
    teacher_display: str
    opening_message: str


class LessonService(Protocol):
    async def start_lesson(self, command: StartLessonCommand) -> StartLessonResult: ...
```

### 4.2 `impl.py`

实现默认业务逻辑，但不得被其他业务模块直接 import。

```python
from .interface import LessonService, StartLessonCommand, StartLessonResult


class DefaultLessonService(LessonService):
    def __init__(self, prompt_builder, llm_client, session_repository):
        self._prompt_builder = prompt_builder
        self._llm_client = llm_client
        self._session_repository = session_repository

    async def start_lesson(self, command: StartLessonCommand) -> StartLessonResult:
        prompt = self._prompt_builder.build_start_prompt(command)
        text = await self._llm_client.complete(prompt)
        session = self._session_repository.create()
        session.add_assistant_message(text)
        self._session_repository.save(session)
        return StartLessonResult(
            teacher_name=prompt.teacher_name,
            teacher_display=prompt.teacher_display,
            opening_message=text,
        )
```

### 4.3 `__init__.py`

只暴露稳定接口、DTO、模型、异常。

```python
from .errors import LessonConflictError, LessonNotFoundError
from .interface import LessonService, StartLessonCommand, StartLessonResult
from .models import LessonSession, Message

__all__ = [
    "LessonService",
    "StartLessonCommand",
    "StartLessonResult",
    "LessonSession",
    "Message",
    "LessonConflictError",
    "LessonNotFoundError",
]
```

禁止：

```python
from .impl import DefaultLessonService  # 禁止在模块 __init__.py 暴露实现类
```

---

## 5. 依赖注入与 Composition Root

所有实现类只能在 `app/container.py` 中实例化。

```python
from dataclasses import dataclass

from project_name.application.lesson_service import LessonApplicationService
from project_name.infrastructure.llm.anthropic_impl import AnthropicLLMClient
from project_name.infrastructure.storage.filesystem_impl import FileStorage
from project_name.modules.lesson.impl import DefaultLessonManager
from project_name.modules.prompt.impl import DefaultPromptBuilder


@dataclass(frozen=True)
class AppContainer:
    lesson_service: LessonApplicationService


def build_container(settings) -> AppContainer:
    file_storage = FileStorage(root=settings.data_dir)
    llm_client = AnthropicLLMClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
    )
    prompt_builder = DefaultPromptBuilder(file_storage=file_storage)
    lesson_manager = DefaultLessonManager(storage=file_storage)

    lesson_service = LessonApplicationService(
        lesson_manager=lesson_manager,
        prompt_builder=prompt_builder,
        llm_client=llm_client,
    )

    return AppContainer(lesson_service=lesson_service)
```

API 层通过依赖函数获取服务：

```python
from fastapi import Request


def get_container(request: Request):
    return request.app.state.container


def get_lesson_service(request: Request):
    return get_container(request).lesson_service
```

测试中使用 fake 实现：

```python
container = AppContainer(
    lesson_service=LessonApplicationService(
        lesson_manager=InMemoryLessonManager(),
        prompt_builder=FakePromptBuilder(),
        llm_client=FakeLLMClient(["hello"]),
    )
)
```

---

## 6. 依赖方向规则

允许：

```text
adapters -> application -> modules.interface
application -> modules.interface
application -> infrastructure.interface
infrastructure.impl -> infrastructure.interface
app.container -> modules.impl + infrastructure.impl
```

禁止：

```text
modules/* -> adapters/*
modules/* -> FastAPI / SQLAlchemy / Anthropic / httpx / boto3
modules/a -> modules/b/impl.py
adapters/* -> modules/*/impl.py
application/* -> modules/*/impl.py
任何非 container 文件 -> infrastructure/*/*_impl.py
```

---

## 7. pyproject.toml 标准模板

```toml
[project]
name = "project-name"
version = "0.1.0"
description = "Python service with modular architecture and engineering governance"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "anthropic>=0.50.0",
  "beautifulsoup4>=4.12.0",
  "fastapi>=0.115.0",
  "httpx>=0.27.0",
  "pydantic>=2.0.0",
  "pydantic-settings>=2.0.0",
  "pymupdf>=1.24.0",
  "python-dotenv>=1.0.0",
  "python-multipart>=0.0.9",
  "tiktoken>=0.7.0",
  "uvicorn>=0.30.0",
]

[project.scripts]
project-name = "project_name.adapters.cli.main:main"

[dependency-groups]
dev = [
  "coverage[toml]>=7.6.0",
  "mypy>=1.11.0",
  "pre-commit>=3.8.0",
  "pytest>=8.3.0",
  "pytest-asyncio>=0.24.0",
  "ruff>=0.6.0",
]

[tool.uv]
package = true

[tool.ruff]
target-version = "py311"
line-length = 100
src = ["src", "tests"]
exclude = [
  ".git",
  ".mypy_cache",
  ".pytest_cache",
  ".ruff_cache",
  ".venv",
  "build",
  "dist",
]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "lf"

[tool.ruff.lint]
select = [
  "E",     # pycodestyle errors
  "F",     # pyflakes
  "I",     # import sorting
  "UP",    # pyupgrade
  "B",     # flake8-bugbear
  "SIM",   # simplify
  "C4",    # comprehensions
  "RUF",   # ruff-specific
]
ignore = [
  "E501",  # line length handled by formatter; long strings may remain
]
fixable = ["ALL"]
unfixable = []

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = [
  "S101",
]

[tool.mypy]
python_version = "3.11"
files = ["src", "tests"]
plugins = []
ignore_missing_imports = true
warn_return_any = true
warn_unused_ignores = true
warn_redundant_casts = true
warn_unreachable = true
no_implicit_optional = true
check_untyped_defs = true
disallow_untyped_defs = false
disallow_incomplete_defs = false
strict_optional = true
show_error_codes = true
pretty = true

[[tool.mypy.overrides]]
module = [
  "fitz.*",
  "tiktoken.*",
]
ignore_missing_imports = true

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
addopts = [
  "-ra",
  "--strict-markers",
  "--strict-config",
]
markers = [
  "unit: fast isolated unit tests",
  "integration: tests that touch real adapters or filesystem",
  "contract: interface contract tests reusable across implementations",
  "architecture: static architecture boundary tests",
  "slow: slow tests excluded from quick local runs",
]
filterwarnings = [
  "error",
]

[tool.coverage.run]
branch = true
source = ["src"]

[tool.coverage.report]
show_missing = true
skip_covered = true
fail_under = 0
```

渐进项目可将 `files = ["src", "tests"]` 临时改成具体新代码目录；旧目录迁移后再扩大范围。

---

## 8. Makefile 标准模板

```makefile
.DEFAULT_GOAL := help

PYTHON_VERSION ?= 3.11
APP_MODULE ?= project_name.adapters.api.app:create_app
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: help sync install install-dev run dev test test-unit test-integration format format-check lint typecheck check pre-commit-install pre-commit-run clean

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "%-24s %s\n", $$1, $$2}'

sync: ## Sync production dependencies
	uv sync

install: sync ## Alias for production install

install-dev: ## Sync production and development dependencies
	uv sync --group dev

run: ## Run service without reload
	uv run uvicorn $(APP_MODULE) --factory --host $(HOST) --port $(PORT)

dev: ## Run service with reload for local development
	uv run uvicorn $(APP_MODULE) --factory --host $(HOST) --port $(PORT) --reload

test: ## Run all tests
	uv run pytest

test-unit: ## Run fast unit tests
	uv run pytest -m "unit or contract or architecture"

test-integration: ## Run integration tests
	uv run pytest -m "integration"

format: ## Format code
	uv run ruff format src tests
	uv run ruff check --fix src tests

format-check: ## Check code formatting
	uv run ruff format --check src tests

lint: ## Run Ruff lint
	uv run ruff check src tests

typecheck: ## Run Mypy
	uv run mypy

check: format-check lint typecheck test ## Run full local/CI quality gate

pre-commit-install: ## Install git pre-commit hook
	uv run pre-commit install

pre-commit-run: ## Run pre-commit against all files
	uv run pre-commit run --all-files

clean: ## Remove local caches
	rm -rf .mypy_cache .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
```

命令用途：

| 命令 | 用途 |
|---|---|
| `make install-dev` | 新开发者初始化 |
| `make dev` | 本地开发启动 |
| `make run` | 本地模拟生产启动 |
| `make format` | 自动格式化和可修复 lint |
| `make check` | 本地与 CI 统一质量门禁 |
| `make pre-commit-install` | 安装提交前 hook |
| `make pre-commit-run` | 手动跑完整 pre-commit |

---

## 9. pre-commit 标准模板

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-format-check
        name: ruff format --check
        entry: uv run ruff format --check src tests
        language: system
        pass_filenames: false

      - id: ruff-check
        name: ruff check
        entry: uv run ruff check src tests
        language: system
        pass_filenames: false

      - id: mypy
        name: mypy
        entry: uv run mypy
        language: system
        pass_filenames: false

      - id: pytest-fast
        name: pytest fast
        entry: uv run pytest -m "unit or contract or architecture"
        language: system
        pass_filenames: false
```

规则：

1. pre-commit 跑快速检查，不默认跑完整 integration/slow 测试。
2. CI 必须跑 `make check`。
3. 如果 hook 过慢，可临时只保留 `ruff format --check` 和 `ruff check`，但 CI 不得降级。
4. 手动完整检查使用 `make check` 或 `make pre-commit-run`。

---

## 10. 服务启动规范

### 10.1 配置

使用 `pydantic-settings` 管理配置。

```python
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "local"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"

    data_dir: Path = Path("data")

    llm_base_url: str = "https://api.example.com"
    llm_model: str = "model-name"
    llm_api_key: str


def load_settings() -> Settings:
    return Settings()
```

### 10.2 FastAPI App Factory

```python
from fastapi import FastAPI

from project_name.app.config import load_settings
from project_name.app.container import build_container
from project_name.adapters.api.routes import router


def create_app() -> FastAPI:
    settings = load_settings()
    container = build_container(settings)

    app = FastAPI(title="Project API")
    app.state.settings = settings
    app.state.container = container
    app.include_router(router, prefix="/api")
    return app
```

### 10.3 启动命令

开发：

```bash
make dev
```

生产或本地模拟生产：

```bash
make run
```

禁止团队成员长期使用手写命令，例如：

```bash
uvicorn some.long.module:app --reload --host 0.0.0.0 --port 8000
```

所有 host、port、reload 策略必须收敛到 Makefile 或部署配置。

---

## 11. `.python-version` 模板

```text
3.11
```

如项目明确依赖 Python 3.12，可改为：

```text
3.12
```

`pyproject.toml` 的 `requires-python` 必须与此保持一致。

---

## 12. `.env.example` 模板

```bash
APP_ENV=local
HOST=127.0.0.1
PORT=8000
LOG_LEVEL=INFO

DATA_DIR=data

LLM_BASE_URL=https://api.example.com
LLM_MODEL=model-name
LLM_API_KEY=replace-me
```

规则：

1. `.env` 不提交。
2. `.env.example` 必须提交。
3. 新增环境变量必须同步更新 `.env.example`。
4. 配置默认值放在 `Settings`，敏感值只从环境变量读取。

---

## 13. GitHub Actions CI 模板

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version-file: ".python-version"

      - name: Sync dependencies
        run: uv sync --group dev

      - name: Run quality gate
        run: make check
```

CI 原则：

1. CI 不重新发明命令，只调用 Makefile。
2. 本地 `make check` 通过，CI 应该基本一致通过。
3. 可后续增加 coverage、测试报告上传、Docker build。

---

## 14. 测试规范

测试目录：

```text
tests/
  unit/              # 单模块、无外部副作用
  application/       # 用例编排测试，使用 fake 依赖
  contract/          # 接口契约测试，不同实现复用
  integration/       # 文件系统/HTTP/API 集成
  architecture/      # import 边界、目录规则、依赖方向
```

规则：

1. Unit 测试不得调用真实 LLM、真实 HTTP、真实生产文件目录。
2. Application 测试必须使用 fake repository / fake llm / fake clock。
3. Infrastructure 测试可以使用临时目录、mock HTTP、测试数据库。
4. API 测试使用测试 container 覆盖真实依赖。
5. Architecture 测试必须检查禁止 import `impl.py` 的规则。

架构边界测试示例：

```python
import ast
from pathlib import Path


def test_only_container_imports_module_impls() -> None:
    root = Path("src/project_name")
    allowed = {root / "app" / "container.py"}

    for file in root.rglob("*.py"):
        if file in allowed:
            continue

        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.endswith(".impl"), f"{file} imports {node.module}"
```

---

## 15. Mypy 渐进路线

### 阶段 1：能跑起来

```toml
disallow_untyped_defs = false
check_untyped_defs = true
ignore_missing_imports = true
```

验收：

```bash
make typecheck
```

可以通过。

### 阶段 2：新代码强类型

对 `src/project_name/modules/**` 和 `src/project_name/application/**` 收紧：

```toml
[[tool.mypy.overrides]]
module = [
  "project_name.modules.*",
  "project_name.application.*",
]
disallow_untyped_defs = true
disallow_incomplete_defs = true
```

### 阶段 3：核心模块 strict

逐步开启：

```toml
strict = true
```

优先顺序：

1. `modules/*/interface.py`
2. `modules/*/models.py`
3. `application/*.py`
4. `infrastructure/*/interface.py`
5. `impl.py`
6. `adapters/`

---

## 16. 从 requirements 迁移到 pyproject

1. 读取现有 `requirements.txt` 和 `requirements-dev.txt`。
2. 将运行时依赖放入 `[project].dependencies`。
3. 将开发工具放入 `[dependency-groups].dev`。
4. 写入 `pyproject.toml`。
5. 执行：

```bash
uv lock
uv sync --group dev
```

6. 新增或更新 `Makefile`。
7. 新增 `.pre-commit-config.yaml`、`.python-version`、`.env.example`。
8. 修改 CI 使用：

```bash
uv sync --group dev
make check
```

9. 删除或废弃：

```text
requirements.txt
requirements-dev.txt
```

10. 验证：

```bash
make dev
make format
make check
```

---

## 17. 渐进落地计划

### 阶段 1：工程入口统一

交付：

- `pyproject.toml`
- `uv.lock`
- `Makefile`
- `.python-version`
- `.env.example`

验收：

```bash
uv sync --group dev
make dev
make test
```

### 阶段 2：格式化与 lint

交付：

- Ruff format 配置
- Ruff check 配置
- `make format`
- `make lint`

验收：

```bash
make format
make lint
```

### 阶段 3：测试与质量门禁

交付：

- Pytest 配置
- marker 分层
- `make check`

验收：

```bash
make check
```

### 阶段 4：pre-commit 与 CI

交付：

- `.pre-commit-config.yaml`
- `.github/workflows/ci.yml`

验收：

```bash
make pre-commit-install
make pre-commit-run
```

PR 上 CI 通过。

### 阶段 5：架构分层和接口治理

交付：

- `modules/*/interface.py`
- `modules/*/impl.py`
- `app/container.py`
- `application/*.py`
- 架构边界测试

验收：

```bash
make check
uv run pytest tests/architecture
```

### 阶段 6：类型收紧和覆盖率

交付：

- 核心模块完整类型标注
- Mypy overrides 收紧
- Coverage 配置

验收：

```bash
make typecheck
uv run coverage run -m pytest
uv run coverage report
```

---

## 18. 代码审查规则清单

架构规则：

- [ ] 新业务能力是否有独立模块。
- [ ] 模块是否包含 `interface.py`、`impl.py`、`models.py`、`errors.py`、`__init__.py`。
- [ ] 跨模块是否只依赖接口。
- [ ] 是否只有 `container.py` import 实现类。
- [ ] API 路由是否没有业务逻辑。
- [ ] 业务模块是否没有直接依赖外部 SDK。
- [ ] 文件、HTTP、LLM、时间、UUID 是否通过接口注入。
- [ ] 是否没有跨文件调用 `_private` 函数或方法。

工程规则：

- [ ] 依赖是否只写在 `pyproject.toml`。
- [ ] 新命令是否收敛到 `Makefile`。
- [ ] 本地和 CI 是否使用同一命令。
- [ ] 是否通过 `make format-check`。
- [ ] 是否通过 `make lint`。
- [ ] 是否通过 `make typecheck`。
- [ ] 是否通过 `make test`。
- [ ] 是否更新 `.env.example`。
- [ ] 是否新增必要测试。

---

## 19. 新项目初始化清单

```bash
uv init --package
uv add fastapi uvicorn pydantic pydantic-settings python-dotenv
uv add --group dev ruff mypy pytest pytest-asyncio pre-commit coverage[toml]
uv lock
```

然后复制本规范中的：

- `pyproject.toml` 工具配置
- `Makefile`
- `.pre-commit-config.yaml`
- `.python-version`
- `.env.example`
- 推荐目录结构
- 架构边界测试

最后执行：

```bash
make install-dev
make format
make check
make pre-commit-install
```

