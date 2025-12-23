#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# 检查Poetry是否安装
if ! command -v poetry &> /dev/null; then
    echo "Poetry未安装。正在安装Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
fi

# 使用Poetry安装项目依赖
poetry install

# 安装开发依赖（如果尚未安装）
poetry install --with dev

echo "✅ 开发环境设置完成！"
