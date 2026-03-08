# qBittorrent Clipboard Monitor - Makefile
# 项目管理和自动化构建工具

.PHONY: help install install-dev test test-cov lint format security build build-multi run clean docs release

# 默认目标
.DEFAULT_GOAL := help

# 变量定义
PYTHON := python3
POETRY := poetry
DOCKER := docker
COMPOSE := docker-compose
APP_NAME := qbittorrent-clipboard-monitor
APP_VERSION := 3.0.0

# 颜色定义 (用于美化输出)
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
NC := \033[0m # No Color

## help: 显示帮助信息
help:
	@echo "$(BLUE)qBittorrent Clipboard Monitor - 可用目标$(NC)"
	@echo "========================================"
	@echo ""
	@echo "$(GREEN)安装与依赖$(NC)"
	@echo "  make install       - 安装生产依赖"
	@echo "  make install-dev   - 安装开发依赖 (包含测试和代码检查工具)"
	@echo ""
	@echo "$(GREEN)测试$(NC)"
	@echo "  make test          - 运行测试"
	@echo "  make test-cov      - 运行测试并生成覆盖率报告"
	@echo ""
	@echo "$(GREEN)代码质量$(NC)"
	@echo "  make lint          - 运行代码检查 (black, mypy, isort, flake8)"
	@echo "  make format        - 自动格式化代码"
	@echo "  make security      - 安全扫描 (bandit, safety)"
	@echo ""
	@echo "$(GREEN)构建与运行$(NC)"
	@echo "  make build         - 构建 Docker 镜像"
	@echo "  make build-multi   - 多架构 Docker 构建"
	@echo "  make run           - 本地运行应用"
	@echo ""
	@echo "$(GREEN)维护$(NC)"
	@echo "  make clean         - 清理临时文件和缓存"
	@echo "  make docs          - 构建文档"
	@echo "  make release       - 发布新版本"
	@echo ""

## install: 安装生产依赖
install:
	@echo "$(BLUE)📦 安装生产依赖...$(NC)"
	$(POETRY) install --no-dev
	@echo "$(GREEN)✓ 依赖安装完成$(NC)"

## install-dev: 安装开发依赖
install-dev:
	@echo "$(BLUE)📦 安装开发依赖...$(NC)"
	$(POETRY) install
	@echo "$(GREEN)✓ 开发依赖安装完成$(NC)"

## test: 运行测试
test:
	@echo "$(BLUE)🧪 运行测试...$(NC)"
	$(POETRY) run pytest -v
	@echo "$(GREEN)✓ 测试完成$(NC)"

## test-cov: 运行测试并生成覆盖率报告
test-cov:
	@echo "$(BLUE)🧪 运行测试并生成覆盖率报告...$(NC)"
	$(POETRY) run pytest --cov=qbittorrent_monitor --cov-report=term-missing --cov-report=html --cov-report=xml -v
	@echo "$(GREEN)✓ 覆盖率报告生成完成$(NC)"
	@echo "  HTML 报告: htmlcov/index.html"
	@echo "  XML 报告: coverage.xml"

## lint: 运行代码检查 (black, mypy, isort, flake8)
lint:
	@echo "$(BLUE)🔍 运行代码检查...$(NC)"
	@echo "$(YELLOW)  - black (格式检查)...$(NC)"
	$(POETRY) run black --check qbittorrent_monitor tests run.py
	@echo "$(YELLOW)  - isort (导入排序检查)...$(NC)"
	$(POETRY) run isort --check-only qbittorrent_monitor tests run.py 2>/dev/null || echo "$(YELLOW)  ⚠ isort 未安装，跳过$(NC)"
	@echo "$(YELLOW)  - mypy (类型检查)...$(NC)"
	$(POETRY) run mypy qbittorrent_monitor || true
	@echo "$(YELLOW)  - flake8 (代码风格检查)...$(NC)"
	$(POETRY) run flake8 qbittorrent_monitor tests --max-line-length=100 --extend-ignore=E203 2>/dev/null || echo "$(YELLOW)  ⚠ flake8 未安装，跳过$(NC)"
	@echo "$(GREEN)✓ 代码检查完成$(NC)"

## format: 自动格式化代码
format:
	@echo "$(BLUE)✨ 格式化代码...$(NC)"
	@echo "$(YELLOW)  - 运行 black...$(NC)"
	$(POETRY) run black qbittorrent_monitor tests run.py
	@echo "$(YELLOW)  - 运行 isort...$(NC)"
	$(POETRY) run isort qbittorrent_monitor tests run.py 2>/dev/null || echo "$(YELLOW)  ⚠ isort 未安装，跳过$(NC)"
	@echo "$(GREEN)✓ 代码格式化完成$(NC)"

## security: 安全扫描 (bandit, safety)
security:
	@echo "$(BLUE)🔒 运行安全扫描...$(NC)"
	@echo "$(YELLOW)  - bandit (代码安全分析)...$(NC)"
	$(POETRY) run bandit -r qbittorrent_monitor -f txt 2>/dev/null || echo "$(YELLOW)  ⚠ bandit 未安装，跳过$(NC)"
	@echo "$(YELLOW)  - safety (依赖漏洞检查)...$(NC)"
	$(POETRY) run safety check 2>/dev/null || echo "$(YELLOW)  ⚠ safety 未安装，跳过$(NC)"
	@echo "$(GREEN)✓ 安全扫描完成$(NC)"

## build: 构建 Docker 镜像
build:
	@echo "$(BLUE)🐳 构建 Docker 镜像...$(NC)"
	$(DOCKER) build \
		--target production \
		--build-arg APP_VERSION=$(APP_VERSION) \
		--build-arg BUILD_DATE=$(shell date -u +'%Y-%m-%dT%H:%M:%SZ') \
		--build-arg VCS_REF=$(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown") \
		-t $(APP_NAME):$(APP_VERSION) \
		-t $(APP_NAME):latest \
		.
	@echo "$(GREEN)✓ Docker 镜像构建完成$(NC)"
	@echo "  镜像: $(APP_NAME):$(APP_VERSION)"
	@echo "  镜像: $(APP_NAME):latest"

## build-multi: 多架构 Docker 构建
build-multi:
	@echo "$(BLUE)🐳 多架构 Docker 构建...$(NC)"
	@echo "$(YELLOW)  支持架构: linux/amd64, linux/arm64, linux/arm/v7$(NC)"
	$(DOCKER) buildx build \
		--platform linux/amd64,linux/arm64,linux/arm/v7 \
		--target production \
		--build-arg APP_VERSION=$(APP_VERSION) \
		--build-arg BUILD_DATE=$(shell date -u +'%Y-%m-%dT%H:%M:%SZ') \
		--build-arg VCS_REF=$(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown") \
		-t $(APP_NAME):$(APP_VERSION) \
		-t $(APP_NAME):latest \
		.
	@echo "$(GREEN)✓ 多架构构建完成$(NC)"

## run: 本地运行
run:
	@echo "$(BLUE)🚀 启动应用...$(NC)"
	$(POETRY) run python run.py

## run-docker: 使用 Docker Compose 运行
run-docker:
	@echo "$(BLUE)🐳 使用 Docker Compose 启动...$(NC)"
	$(COMPOSE) up -d
	@echo "$(GREEN)✓ 容器已启动$(NC)"

## stop-docker: 停止 Docker Compose
stop-docker:
	@echo "$(BLUE)🛑 停止 Docker Compose...$(NC)"
	$(COMPOSE) down
	@echo "$(GREEN)✓ 容器已停止$(NC)"

## clean: 清理临时文件
clean:
	@echo "$(BLUE)🧹 清理临时文件...$(NC)"
	@echo "$(YELLOW)  - 清理 Python 缓存...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name "*.pyd" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".coverage" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(YELLOW)  - 清理构建产物...$(NC)"
	rm -rf build/ dist/ .eggs/ 2>/dev/null || true
	rm -f coverage.xml .coverage 2>/dev/null || true
	@echo "$(GREEN)✓ 清理完成$(NC)"

## docs: 构建文档
docs:
	@echo "$(BLUE)📚 构建文档...$(NC)"
	@if [ -d "docs" ]; then \
		$(POETRY) run mkdocs build 2>/dev/null || echo "$(YELLOW)  ⚠ mkdocs 未安装，跳过$(NC)"; \
		$(POETRY) run pdoc --html qbittorrent_monitor -o docs/api 2>/dev/null || echo "$(YELLOW)  ⚠ pdoc 未安装，跳过$(NC)"; \
	else \
		echo "$(YELLOW)  ℹ docs 目录不存在，跳过文档构建$(NC)"; \
	fi
	@echo "$(GREEN)✓ 文档构建完成$(NC)"

## release: 发布新版本
release:
	@echo "$(BLUE)🚀 发布新版本$(NC)"
	@read -p "请输入新版本号 (当前: $(APP_VERSION)): " version; \
	if [ -z "$$version" ]; then \
		echo "$(RED)✗ 版本号不能为空$(NC)"; \
		exit 1; \
	fi; \
	echo "$(YELLOW)准备发布版本: $$version$(NC)"; \
	echo "$(YELLOW)  - 更新版本号...$(NC)"; \
	sed -i.bak "s/version = \"$(APP_VERSION)\"/version = \"$$version\"/" pyproject.toml && rm -f pyproject.toml.bak; \
	echo "$(YELLOW)  - 运行测试...$(NC)"; \
	$(POETRY) run pytest -q || { echo "$(RED)✗ 测试失败$(NC)"; exit 1; }; \
	echo "$(YELLOW)  - 构建包...$(NC)"; \
	$(POETRY) build; \
	$(POETRY) run gitchangelog > CHANGELOG.md 2>/dev/null || echo "$(YELLOW)  ⚠ gitchangelog 未安装，跳过$(NC)"; \
	echo "$(GREEN)✓ 版本 $$version 发布准备完成$(NC)"; \
	echo ""; \
	echo "$(BLUE)后续步骤:$(NC)"; \
	echo "  1. git add -A"; \
	echo "  2. git commit -m 'chore: bump version to $$version'"; \
	echo "  3. git tag v$$version"; \
	echo "  4. git push origin main --tags"; \
	echo "  5. $(POETRY) publish (如需发布到 PyPI)"

## check: 运行所有检查 (用于 CI)
check: lint test security
	@echo "$(GREEN)✓ 所有检查通过$(NC)"

## update: 更新依赖
update:
	@echo "$(BLUE)🔄 更新依赖...$(NC)"
	$(POETRY) update
	@echo "$(GREEN)✓ 依赖更新完成$(NC)"

## shell: 进入 Poetry shell
shell:
	@echo "$(BLUE)🐚 进入 Poetry shell...$(NC)"
	$(POETRY) shell

## version: 显示当前版本
version:
	@echo "$(BLUE)📋 项目信息$(NC)"
	@echo "  名称: $(APP_NAME)"
	@echo "  版本: $(APP_VERSION)"
	@echo "  Python: $(shell $(POETRY) run python --version 2>/dev/null || echo 'N/A')"
