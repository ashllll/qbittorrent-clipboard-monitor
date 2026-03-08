#!/bin/bash
# =============================================================================
# 代码格式化脚本
# 一键运行 black、isort、autoflake 格式化代码
# =============================================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}  qBittorrent Monitor - 代码格式化工具${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""

# 检查虚拟环境
if [ -d ".venv" ]; then
    echo -e "${YELLOW}激活虚拟环境...${NC}"
    source .venv/bin/activate 2>/dev/null || true
elif [ -d "venv" ]; then
    echo -e "${YELLOW}激活虚拟环境...${NC}"
    source venv/bin/activate 2>/dev/null || true
fi

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}错误: $1 未安装${NC}"
        echo -e "${YELLOW}请运行: pip install $1${NC}"
        return 1
    fi
    return 0
}

# 运行格式化工具
run_formatter() {
    local name="$1"
    local cmd="$2"
    
    echo -e "${BLUE}[$name]${NC} 正在运行..."
    if eval "$cmd"; then
        echo -e "${GREEN}[$name]${NC} ✓ 完成"
    else
        echo -e "${RED}[$name]${NC} ✗ 失败"
        return 1
    fi
    echo ""
}

# ========== 1. autoflake: 移除未使用的导入和变量 ==========
if check_command autoflake; then
    run_formatter "autoflake" \
        "autoflake --in-place --recursive --remove-all-unused-imports --remove-unused-variables --expand-star-imports qbittorrent_monitor tests"
fi

# ========== 2. isort: 导入排序 ==========
if check_command isort; then
    run_formatter "isort" \
        "isort qbittorrent_monitor tests --profile black --line-length 100"
fi

# ========== 3. black: 代码格式化 ==========
if check_command black; then
    run_formatter "black" \
        "black qbittorrent_monitor tests --line-length 100 --target-version py39"
fi

echo -e "${GREEN}===============================================${NC}"
echo -e "${GREEN}  代码格式化完成!${NC}"
echo -e "${GREEN}===============================================${NC}"

# 统计修改的文件数量（可选）
if command -v git &> /dev/null && git rev-parse --git-dir &> /dev/null 2>&1; then
    MODIFIED=$(git diff --name-only 2>/dev/null | wc -l | tr -d ' ')
    if [ "$MODIFIED" -gt 0 ]; then
        echo -e "${YELLOW}提示: 有 $MODIFIED 个文件被修改，请记得提交更改。${NC}"
    fi
fi

exit 0
