.PHONY: help ensure-python ensure-uv sync install run dev test test-unit test-integration format format-check lint lint-fix typecheck lock-check check pre-commit-install pre-commit-run clean venv

export PATH := $(HOME)/.local/bin:$(PATH)
PYTHON ?= python3
UV ?= $(HOME)/.local/bin/uv

help:
	@echo "苏格拉底·七 开发命令"
	@echo ""
	@echo "  make install           一键环境搭建 (安装 Python + uv + venv + 依赖 + pre-commit)"
	@echo "  make sync              同步依赖 (uv sync --group dev)"
	@echo "  make run               生产模式启动服务"
	@echo "  make dev               开发模式启动 (uv run uvicorn web.server:app --reload)"
	@echo "  make test              运行全部测试"
	@echo "  make test-unit         运行快速单元测试 (跳过 slow)"
	@echo "  make format            自动格式化代码"
	@echo "  make format-check      检查格式 (CI 用)"
	@echo "  make lint              Lint 检查"
	@echo "  make lint-fix          Lint 自动修复"
	@echo "  make typecheck         类型检查 (mypy)"
	@echo "  make lock-check        检查 uv.lock 与 pyproject.toml 是否同步"
	@echo "  make check             完整检查 (format-check + lint + typecheck + test)"
	@echo "  make pre-commit-install 安装 git 提交前钩子"
	@echo "  make pre-commit-run    手动运行所有 pre-commit hooks"
	@echo "  make venv              重建虚拟环境 (删除 .venv 后重新 uv sync)"
	@echo "  make clean             清理缓存和构建产物"

ensure-python:
	@$(UV) python install --no-prompt 2>/dev/null || true
	@$(UV) python pin 3.12 --no-prompt 2>/dev/null || true

ensure-uv:
	@if [ ! -x "$(UV)" ]; then \
		if command -v curl >/dev/null 2>&1 && curl -LsSf https://astral.sh/uv/install.sh | sh; then \
			:; \
		else \
			$(PYTHON) -m pip install --user uv; \
			USER_BASE="$$( $(PYTHON) -m site --user-base )"; \
			if [ -x "$$USER_BASE/bin/uv" ]; then \
				mkdir -p "$(dir $(UV))"; \
				ln -sf "$$USER_BASE/bin/uv" "$(UV)"; \
			fi; \
		fi; \
	fi
	@$(UV) --version >/dev/null

sync: ensure-uv
	$(UV) sync --group dev

install: ensure-python ensure-uv
	$(UV) sync --group dev
	$(UV) run pre-commit install 2>/dev/null || true
	@echo ""
	@echo "✓ 环境搭建完成"
	@echo "  Python  : $$($(UV) run python --version)"
	@echo "  venv    : .venv/"
	@echo "  下一步  : cp web/.env.example web/.env  # 填入 ANTHROPIC_API_KEY"
	@echo "           make dev                        # 启动开发服务器"

run: ensure-uv
	$(UV) run python web/server.py

dev: ensure-uv
	$(UV) run uvicorn web.server:app --host 0.0.0.0 --port 8000 --reload

test: ensure-uv
	$(UV) run pytest

test-unit: ensure-uv
	$(UV) run pytest -m "not slow"

test-integration: ensure-uv
	$(UV) run pytest -m "integration"

format: ensure-uv
	$(UV) run ruff format web/

format-check: ensure-uv
	$(UV) run ruff format --check web/

lint: ensure-uv
	$(UV) run ruff check web/

lint-fix: ensure-uv
	$(UV) run ruff check --fix web/

typecheck: ensure-uv
	$(UV) run mypy --explicit-package-bases web/server.py web/socratic/

lock-check: ensure-uv
	$(UV) lock --check

check: lock-check format-check lint typecheck test
	@echo "✓ 全部检查通过"

pre-commit-install: ensure-uv
	$(UV) run pre-commit install

pre-commit-run: ensure-uv
	$(UV) run pre-commit run --all-files

venv: ensure-uv
	rm -rf .venv
	$(UV) sync --group dev
	@echo "✓ 虚拟环境已重建"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .ruff_cache
	@echo "清理完成"
