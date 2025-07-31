.PHONY: help install install-dev test test-cov lint format type-check clean build docs serve-docs pre-commit-setup pre-commit-run

# 默认目标
help:
	@echo "可用命令:"
	@echo "  install        安装项目依赖"
	@echo "  install-dev    安装开发依赖"
	@echo "  test           运行测试"
	@echo "  test-cov       运行测试并生成覆盖率报告"
	@echo "  lint           运行代码检查"
	@echo "  format         格式化代码"
	@echo "  type-check     运行类型检查"
	@echo "  clean          清理构建文件"
	@echo "  build          构建分发包"
	@echo "  docs           生成文档"
	@echo "  serve-docs     在本地提供文档服务"
	@echo "  pre-commit-setup 设置pre-commit钩子"
	@echo "  pre-commit-run  运行pre-commit检查"

# 安装项目依赖
install:
	pip install -r requirements.txt
	pip install -e .

# 安装开发依赖
install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pip install -e .

# 运行测试
test:
	pytest

# 运行测试并生成覆盖率报告
test-cov:
	pytest --cov=qbittorrent_monitor --cov-report=html --cov-report=term

# 运行代码检查
lint:
	flake8 qbittorrent_monitor tests

# 格式化代码
format:
	black qbittorrent_monitor tests
	isort qbittorrent_monitor tests

# 运行类型检查
type-check:
	mypy qbittorrent_monitor

# 清理构建文件
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# 构建分发包
build: clean
	python -m build

# 生成文档
docs:
	sphinx-build -b html docs/source docs/build

# 在本地提供文档服务
serve-docs: docs
	cd docs/build && python -m http.server 8000

# 设置pre-commit钩子
pre-commit-setup:
	pre-commit install

# 运行pre-commit检查
pre-commit-run:
	pre-commit run --all-files

# 开发环境设置
dev-setup: install-dev pre-commit-setup

# 发布前检查
release-check: format lint type-check test
	@echo "所有检查通过，可以发布！"