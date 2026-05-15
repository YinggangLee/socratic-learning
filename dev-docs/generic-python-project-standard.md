# 生产级 Python 项目工程化与架构规范

> 适用：Web 服务、CLI 工具、数据处理管道、后台任务等多人协作 Python 项目。
> 本文独立于任何具体项目，提供可直接落地的最小可行标准。

---

## 1. 项目结构

### 1.1 两种推荐布局

**库/包项目**（发布到 PyPI 或被其他项目 import）：

```text
myproject/
  pyproject.toml
  src/
    myproject/
      __init__.py
      app/
      modules/
      infrastructure/
      adapters/
  tests/
```

**应用/服务项目**（独立部署，不需要被打包 import）：

```text
myproject/
  pyproject.toml
  myproject/
    __init__.py
    server.py          # 入口
    app/
    modules/
    infrastructure/
    adapters/
  tests/
```

选择依据：如果其他项目会 `pip install` 或 `from myproject import ...`，用 `src/` 布局。如果是独立服务，用平铺布局即可。`src/` 布局能防止意外导入未安装的本地代码，是更安全的选择。

### 1.2 反模式

- 把所有代码堆在根目录的 `utils.py`、`helpers.py`、`common.py`
- 按技术类型分层（`models/`、`views/`、`controllers/`）而非按业务能力
- 一个文件超过 500 行不拆分
- `__init__.py` 中写业务逻辑

---

## 2. 分层架构

### 2.1 四层模型

```
adapters/       ← HTTP、CLI、消息队列等外部入口
  ↓ 依赖
application/    ← 用例编排、事务边界、权限校验
  ↓ 依赖
modules/        ← 纯业务逻辑、领域模型、业务规则
  ↑ 实现
infrastructure/ ← 数据库、缓存、文件系统、外部 API 等技术实现
```

### 2.2 各层规则

**adapters（入口适配层）**
- 可以做的事：解析 HTTP 请求、调用 application service、序列化响应、处理认证
- 不能做的事：包含业务判断、直接操作数据库、直接调用外部 API
- 一个 route handler 超过 15 行通常意味着业务逻辑泄漏

**application（应用服务层）**
- 可以做的事：编排多个模块完成一个用例、管理事务、发出领域事件
- 不能做的事：直接 import 数据库驱动、直接 new HTTP client
- 一个 service 方法应该是"做什么"的清单，不是"怎么做"的细节

**modules（业务模块层）**
- 每个模块是一个独立业务能力，如 `modules/payment/`、`modules/notification/`
- 模块结构：
  ```text
  modules/payment/
    interface.py   # Protocol/ABC：对外暴露的契约
    impl.py        # 默认实现（只能被 container 实例化）
    models.py      # 领域模型、值对象、枚举
    errors.py      # 本模块的异常类型
  ```
- 模块之间只能通过 `interface.py` 通信
- 模块绝对不能 import FastAPI、SQLAlchemy、requests、boto3 等外部技术

**infrastructure（基础设施层）**
- 每个技术能力一个子包：`llm/`、`storage/`、`cache/`、`queue/`
- 必须定义 `interface.py`（抽象）和 `impl.py`（具体实现）
- 可以同时提供 fake 实现用于测试：

  ```text
  infrastructure/llm/
    interface.py
    openai_impl.py
    fake_impl.py        # 测试用
  ```

### 2.3 依赖注入

所有具体实现类的实例化只能发生在一个地方——Composition Root：

```python
# app/container.py — 唯一允许 import 所有 impl 的文件
def build_container(settings: Settings) -> AppContainer:
    llm_client = OpenAIImpl(api_key=settings.llm_key)
    payment_gateway = StripeImpl(secret=settings.stripe_secret)
    payment_service = PaymentService(gateway=payment_gateway)
    return AppContainer(payment_service=payment_service, ...)
```

测试中直接手写 container，注入 fake 实现：

```python
container = AppContainer(
    payment_service=PaymentService(gateway=FakePaymentGateway()),
)
```

---

## 3. 接口优先设计

### 3.1 先写契约

任何新功能的第一步不是写实现，而是写接口：

```python
# modules/notification/interface.py
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SendNotificationCommand:
    user_id: str
    title: str
    body: str
    channel: str  # "email" | "sms" | "push"


@dataclass(frozen=True)
class SendNotificationResult:
    notification_id: str
    delivered: bool


class NotificationSender(Protocol):
    async def send(self, command: SendNotificationCommand) -> SendNotificationResult: ...
```

### 3.2 接口设计原则

- 用 `Protocol` 做接口（比 ABC 更轻量，支持 duck typing）
- 输入输出用 frozen dataclass 或 Pydantic model
- 一个接口方法只做一件事
- 接口名体现能力：`XxxSender`、`XxxRepository`、`XxxGateway`、`XxxRenderer`
- 不要一个接口里有 10 个方法——拆成多个小接口

### 3.3 异常设计

每个模块定义自己的异常，不要跨模块抛裸 Exception：

```python
# modules/payment/errors.py
class PaymentError(Exception): ...          # 基类
class PaymentDeclined(PaymentError): ...     # 具体错误
class PaymentTimeout(PaymentError): ...
```

Application 层负责把模块异常转换成 API 层能理解的错误表示。

---

## 4. 依赖管理

### 4.1 工具选择

首选 `uv`。理由：速度快（Rust 实现）、PEP 621 兼容、锁文件可靠、`uv run` 统一命令执行。

### 4.2 pyproject.toml 结构

```toml
[project]
name = "myproject"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    # 运行时依赖：服务启动必须的包
]

[dependency-groups]
dev = [
    # 开发时依赖：lint、test、typecheck、format
]

[tool.ruff]        # 格式化 + lint
[tool.mypy]        # 类型检查
[tool.pytest]      # 测试
```

### 4.3 依赖分类

| 类别 | 放哪里 | 例子 |
|------|--------|------|
| 运行时 | `[project].dependencies` | fastapi、sqlalchemy、httpx |
| 开发工具 | `[dependency-groups].dev` | ruff、mypy、pytest、pre-commit |
| 测试辅助 | `[dependency-groups].dev` | pytest-asyncio、coverage、faker |
| 可选功能 | `[project.optional-dependencies]` | 特定数据库驱动、云服务 SDK |

### 4.4 不要做的事

- 维护 `requirements.txt` + `requirements-dev.txt` 作为主要依赖源
- 把开发工具放进生产依赖
- 不锁版本（`uv lock` 生成 `uv.lock`，提交到 git）

---

## 5. Makefile 统一入口

### 5.1 设计原则

- 每个 `make xxx` 对应一个明确操作
- 本地开发和 CI 用完全相同的命令
- 新成员 clone 后只需 `make install` 就能进入开发
- 不要手写长命令（`uvicorn src.app:app --reload --host 0.0.0.0 ...`）

### 5.2 最小命令集

```makefile
make install       # 一键搭建环境（装 Python + uv + venv + 依赖 + pre-commit）
make sync          # 同步依赖
make dev           # 开发模式启动（带 reload）
make run           # 生产模式启动
make test          # 全部测试
make test-unit     # 快速测试（不含 slow）
make format        # 自动格式化
make format-check  # 格式检查（CI 用）
make lint          # Lint 检查
make typecheck     # 类型检查
make check         # 完整质量门禁（format-check + lint + typecheck + test）
make clean         # 清理缓存
```

### 5.3 `make install` 应该做什么

```makefile
install: ensure-python ensure-uv
    uv sync --group dev
    uv run pre-commit install || true
    @echo "✓ 环境就绪。下一步：cp .env.example .env  # 填入密钥"
```

`ensure-python` 利用 `uv python install` 根据 `.python-version` 自动下载对应 Python 版本。`ensure-uv` 通过 curl 或 pip 安装 uv。

---

## 6. 代码质量

### 6.1 格式化：Ruff

```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

一个人的偏好不该成为团队辩论话题。用 Ruff 统一格式化，保存时自动执行，不要讨论"这里该不该换行"。

### 6.2 Lint：Ruff

```toml
[tool.ruff.lint]
select = [
    "E",     # pycodestyle errors
    "F",     # pyflakes (未使用变量、未定义名称等)
    "I",     # import 排序
    "UP",    # pyupgrade (用新语法替换旧写法)
    "B",     # bugbear (常见 bug 模式)
    "SIM",   # 简化建议
    "RUF",   # Ruff 特有规则
]
```

lint 规则宁可先宽松再收紧，不要一开始就设几百条规则导致全员抵触。渐进式新增规则。

### 6.3 类型检查：Mypy

**渐进路线：**

| 阶段 | 配置 | 目标 |
|------|------|------|
| 1 | `ignore_missing_imports=true`、`disallow_untyped_defs=false` | 能跑起来，零报错 |
| 2 | 对核心模块开启 `disallow_untyped_defs=true` | 新代码强类型 |
| 3 | `warn_return_any=true`、`strict_optional=true` | 消除常见类型漏洞 |
| 4 | `strict=true` | 生产级类型安全 |

用 `[[tool.mypy.overrides]]` 对不同目录设置不同严格度：

```toml
[[tool.mypy.overrides]]
module = ["myproject.modules.*", "myproject.application.*"]
disallow_untyped_defs = true

[[tool.mypy.overrides]]
module = ["myproject.adapters.*"]
disallow_untyped_defs = false  # API 路由可以松一点
```

### 6.4 Pre-commit

提交前自动运行快速检查（不跑慢测试）：

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

pre-commit hook 超过 10 秒就开始影响开发体验。如果 mypy 太慢，可以暂时只放 format + lint，mypy 留给 CI。

---

## 7. 测试策略

### 7.1 测试金字塔

```text
        /\
       /E2E\          极少：关键用户路径 1-2 条
      /------\
     / 集成测试 \       少量：API + 数据库 + 外部服务 mock
    /----------\
   /  应用服务测试 \     中量：fake 依赖、用例完整性
  /--------------\
 /   单元测试 / 契约测试 \  大量：模块逻辑、接口契约
/------------------\
```

### 7.2 目录组织

```text
tests/
  unit/              # 纯逻辑，不碰 IO
  contract/          # 接口契约，验证不同实现遵循同一接口
  application/       # 用例测试，用 fake 替代真实依赖
  integration/       # 真实文件系统、测试数据库、HTTP client
  architecture/      # import 边界、分层规则
```

### 7.3 测试原则

- 单元测试不调真实 LLM、不发真实 HTTP、不写真实文件
- 应用服务测试用 fake repository、fake gateway、fake clock
- 一个测试只验证一个行为
- 测试名描述场景：`test_payment_declined_when_balance_insufficient`
- 不要为了覆盖率写无意义测试
- 集成测试可以有单独的 `make test-integration`，不在 pre-commit 中跑

### 7.4 Markers

```toml
[tool.pytest.ini_options]
markers = [
    "unit: 快速单元测试",
    "integration: 需要外部依赖的测试",
    "slow: 慢速测试（LLM 调用、大数据处理）",
    "contract: 接口契约测试",
    "architecture: 架构边界检查",
]
```

快速命令：
```bash
make test-unit     # pytest -m "not slow and not integration"
make test          # pytest（全部）
```

---

## 8. 架构约束自动化

### 8.1 Import 边界检查

用一个 AST 扫描脚本确保依赖方向不被破坏：

```python
def test_only_container_imports_impl():
    """只有 app/container.py 可以 import 任何 impl.py"""
    root = Path("src/myproject")
    allowed = {root / "app" / "container.py"}

    for file in root.rglob("*.py"):
        if file in allowed:
            continue
        tree = ast.parse(file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.endswith(".impl"), \
                    f"{file} imports {node.module}"
```

### 8.2 分层检查

```python
def test_modules_dont_import_infrastructure_impl():
    """业务模块不依赖基础设施的具体实现"""
    ...

def test_modules_dont_import_web_frameworks():
    """业务模块不依赖 FastAPI/Django/Flask"""
    ...
```

这些测试放在 `tests/architecture/`，随 `make test-unit` 一起跑，几毫秒执行完。一旦有人写出违规 import，CI 立刻报错。

---

## 9. 配置管理

### 9.1 环境变量

使用 `pydantic-settings` 统一管理：

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    app_env: str = "local"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    database_url: str = "postgresql://localhost:5432/myapp"
    llm_api_key: str  # 无默认值：必须设置
```

原则：
- 每个配置项有明确的类型（`str`、`int`、`bool`）
- 敏感信息无默认值，启动时缺了直接报错
- 非敏感信息有合理的开发默认值
- `.env` 不提交，`.env.example` 必须提交
- 新增环境变量同步更新 `.env.example`

---

## 10. 错误处理

### 10.1 分层错误策略

```
adapters      → 捕获所有异常，转成 HTTP 状态码 / 用户可读消息
application   → 捕获模块异常，转成应用级错误
modules       → 抛出模块专属异常，不关心 HTTP
infrastructure → 包装外部 SDK 异常，转成基础设施异常
```

### 10.2 具体规则

- 永远不要让 SDK 的原始异常穿透到 API 响应里
- exception handler 中 logger.exception() 记录完整 traceback
- 给用户的消息可以模糊（"服务暂时不可用"），给日志的消息必须精确
- except 子句要具体：`except requests.Timeout` 而非 `except Exception`
- 不要 `except: pass` 吞掉异常不留痕迹，至少 `logger.warning("ignored", exc_info=True)`

### 10.3 常见 Bug 模式

以下是实际项目中频繁出现的错误处理漏洞：

**1. except 漏了异常类型**

```python
# 错误
except (json.JSONDecodeError, KeyError):
    pass
# 如果 dict 解包失败还会抛 TypeError

# 正确
except (json.JSONDecodeError, KeyError, TypeError):
    pass
```

**2. JSON 解析没有降级路径**

```python
# 错误：文件损坏直接崩溃
data = json.loads(path.read_text())

# 正确：降级到空数据
try:
    data = json.loads(path.read_text())
except json.JSONDecodeError:
    data = {"items": []}
```

**3. 流式传输不检测客户端断开**

```python
# 错误：客户端断开后服务器继续消耗资源
async for chunk in stream:
    yield chunk

# 正确：检测断开后停止
async for chunk in stream:
    if await request.is_disconnected():
        break
    yield chunk
```

**4. 后台任务返回值未存储**

```python
# 错误：task 可能被 GC
asyncio.create_task(background_work())

# 正确：持有引用防止 GC
self._pending_tasks.add(asyncio.create_task(background_work()))
```

---

## 11. 并发与异步

### 11.1 规则

- 异步函数中不要调用同步阻塞 I/O（`path.read_text()`、`requests.get()`）
- 同步阻塞操作用 `await asyncio.to_thread()` 或专用线程池
- 共享状态用 `asyncio.Lock` 保护
- 不要在 `__init__` 中做 I/O

### 11.2 SSE / Streaming

- 必须检测 `request.is_disconnected()`
- 流中断时，已接收的部分数据要持久化
- 给客户端的错误事件要有结构化的 `type` 和 `code` 字段

---

## 12. 安全

### 12.1 最低要求

- `.env` 和任何含密钥的文件必须在 `.gitignore` 中
- API key、数据库密码、JWT secret 只能从环境变量读取，不能有硬编码默认值
- 用户输入必须校验（Pydantic 做第一道防线）
- 文件上传必须限制大小
- CORS 不要配 `allow_origins=["*"]` + `allow_credentials=True`（这两个互斥）

### 12.2 依赖安全

- 定期 `uv lock --upgrade` 更新依赖
- 关注 `uv pip audit` 或 `safety` 检查已知漏洞
- 不要依赖过时未维护的包

---

## 13. 日志

### 13.1 规则

- 使用标准 `logging` 模块，不要 `print()`
- 生产环境日志级别 INFO，开发环境 DEBUG
- 结构化日志优于文本拼接：`logger.info("user login", extra={"user_id": uid})`
- 错误日志必须包含足够上下文用于排查：谁、什么时候、什么操作、什么输入

### 13.2 日志级别

| 级别 | 用途 |
|------|------|
| DEBUG | 开发调试细节 |
| INFO | 关键业务事件（请求到达、任务完成、配置变更） |
| WARNING | 可恢复的异常（重试成功、降级处理） |
| ERROR | 需要人工关注的错误（API 调用失败、数据损坏） |
| CRITICAL | 服务不可用 |

---

## 14. CI/CD

### 14.1 CI 最小配置

```yaml
# .github/workflows/ci.yml
steps:
  - uses: actions/checkout@v4
  - uses: astral-sh/setup-uv@v5
  - run: uv sync --group dev
  - run: make check
```

### 14.2 原则

- CI 只跑 `make check`，不自己发明命令
- 本地 `make check` 过了，CI 就应该过
- CI 缓存 `.venv` 和 uv cache 可以显著加速
- PR 合并前必须 CI 全绿

---

## 15. 渐进落地路线

不需要一次性做到完美。按以下阶段推进：

**阶段 1：工程入口统一（1-2 小时）**
- 建立 `pyproject.toml` + `Makefile` + `.python-version`
- `make install` 能跑、`make dev` 能启动
- 验收：新成员 clone 后一条命令进入开发

**阶段 2：代码质量基线（2-4 小时）**
- Ruff format + check 配置
- `make format` + `make lint` 通过
- 验收：全部代码格式化一致，无 lint 错误

**阶段 3：测试框架（持续）**
- Pytest 配置 + marker 分层
- `make test` 通过
- 验收：至少核心模块有测试

**阶段 4：提交前检查（30 分钟）**
- `.pre-commit-config.yaml` + `make pre-commit-install`
- 验收：`git commit` 自动触发检查

**阶段 5：CI 接入（1 小时）**
- GitHub Actions（或其他 CI）配置
- 验收：PR 上 CI 通过

**阶段 6：架构分层（持续，视项目规模）**
- 按业务模块拆分，定义接口
- Composition Root + 依赖注入
- 架构边界测试
- 验收：`tests/architecture/` 通过

**阶段 7：类型收紧（持续）**
- Mypy 从宽松逐步收紧
- 核心模块先达到 strict
- 验收：`make typecheck` 零错误

---

## 16. 新项目初始化清单

```bash
# 1. 创建项目
uv init --package
# 或无 package 模式
# uv init --no-package

# 2. 设 Python 版本
echo "3.12" > .python-version

# 3. 加依赖
uv add fastapi uvicorn pydantic pydantic-settings python-dotenv
uv add --group dev ruff mypy pytest pytest-asyncio pre-commit coverage

# 4. 复制模板文件
# - pyproject.toml 中的 [tool.ruff]、[tool.mypy]、[tool.pytest] 配置
# - Makefile
# - .pre-commit-config.yaml
# - .env.example
# - .gitignore

# 5. 初始化环境
make install
make format
make check
```

---

## 附录 A：Makefile 完整模板

```makefile
.DEFAULT_GOAL := help

PYTHON_VERSION ?= 3.12
APP_MODULE ?= myproject.server:app
HOST ?= 127.0.0.1
PORT ?= 8000

export PATH := $(HOME)/.local/bin:$(PATH)
UV ?= $(HOME)/.local/bin/uv

.PHONY: help install sync dev run test test-unit format format-check lint lint-fix typecheck check pre-commit-install pre-commit-run clean venv

help:
	@echo "make install      一键环境搭建"
	@echo "make sync         同步依赖"
	@echo "make dev          开发模式启动"
	@echo "make run          生产模式启动"
	@echo "make test         全部测试"
	@echo "make test-unit    快速测试"
	@echo "make format       自动格式化"
	@echo "make format-check 格式检查"
	@echo "make lint         Lint"
	@echo "make typecheck    类型检查"
	@echo "make check        完整质量门禁"
	@echo "make venv         重建虚拟环境"
	@echo "make clean        清理缓存"

ensure-python:
	@$(UV) python install --no-prompt 2>/dev/null || true

ensure-uv:
	@if [ ! -x "$(UV)" ]; then \
		curl -LsSf https://astral.sh/uv/install.sh | sh || \
		python3 -m pip install --user uv; \
	fi
	@$(UV) --version >/dev/null

install: ensure-python ensure-uv
	$(UV) sync --group dev
	$(UV) run pre-commit install 2>/dev/null || true
	@echo "✓ 环境就绪"

sync: ensure-uv
	$(UV) sync --group dev

dev: ensure-uv
	$(UV) run uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

run: ensure-uv
	$(UV) run uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT)

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

pre-commit-install: ensure-uv
	$(UV) run pre-commit install

pre-commit-run: ensure-uv
	$(UV) run pre-commit run --all-files

venv: ensure-uv
	rm -rf .venv
	$(UV) sync --group dev

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .pytest_cache .ruff_cache
```

---

## 附录 B：pyproject.toml 工具配置片段

可复制到项目 `pyproject.toml` 中，调整 `src` 路径和 Python 版本：

```toml
[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]
exclude = [".git", ".venv", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__", "build", "dist"]

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

---

## 附录 C：代码审查清单

每次 code review 过一遍：

**架构**
- [ ] 新功能是否放在合适的模块/分层
- [ ] 跨模块调用是否通过接口而非实现类
- [ ] 是否有 `impl.py` 被非 container 文件 import
- [ ] API route 是否只做适配（解析请求 → 调 service → 返回响应），没有业务逻辑
- [ ] 业务模块是否无 FastAPI/数据库 SDK/HTTP SDK 等外部技术依赖

**可靠性**
- [ ] except 是否捕获了所有可能的异常类型
- [ ] JSON/文件解析是否有降级路径
- [ ] 流式/异步代码是否有断开检测
- [ ] 后台任务返回值是否被持有引用
- [ ] 文件 I/O 是否在异步函数中使用了同步方法

**安全**
- [ ] 密钥/密码是否只从环境变量读取
- [ ] 用户输入是否有校验
- [ ] 文件上传是否有大小限制
- [ ] CORS 配置是否合理

**工程**
- [ ] 新依赖是否加入 `pyproject.toml`
- [ ] `.env.example` 是否同步更新
- [ ] 是否有测试
- [ ] `make check` 是否通过
