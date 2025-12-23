#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# 检查Poetry是否安装
if ! command -v poetry &> /dev/null; then
    echo "错误: Poetry未安装。请先安装Poetry："
    echo "curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

# 使用Poetry运行测试
poetry run pytest -v "$@"
