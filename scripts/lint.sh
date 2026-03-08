#!/bin/bash
# =============================================================================
# 代码检查脚本
# 一键运行 flake8、mypy、bandit 进行代码质量检查
# =============================================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 统计失败次数
FAILURES=0

# 检查虚拟环境
if [ -d ".venv" ]; then
    echo -e "${YELLOW}激活虚拟环境...${NC}"
    source .venv/bin/activate 2>/dev/null || true
elif [ -d "venv" ]; then
    echo -e "${YELLOW}激活虚拟环境...${NC}"
    source venv/bin/activate 2>/dev/null || true
fi

echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}  qBittorrent Monitor - 代码质量检查工具${NC}"
echo -e "${BLUE}===============================================${NC}"
echo ""

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}错误: $1 未安装${NC}"
        echo -e "${YELLOW}请运行: pip install $1${NC}"
        return 1
    fi
    return 0
}

# 运行检查工具
run_linter() {
    local name="$1"
    local cmd="$2"
    
    echo -e "${CYAN}===============================================${NC}"
    echo -e "${CYAN}[$name]${NC} 正在运行..."
    echo -e "${CYAN}===============================================${NC}"
    
    if eval "$cmd"; then
        echo ""
        echo -e "${GREEN}[$name]${NC} ✓ 检查通过"
        return 0
    else
        echo ""
        echo -e "${RED}[$name]${NC} ✗ 发现问题"
        return 1
    fi
}

# ========== 1. flake8: 代码风格和复杂度检查 ==========
if check_command flake8; then
    if ! run_linter "flake8" \
        "flake8 qbittorrent_monitor tests --max-line-length=100 --max-complexity=10 --extend-ignore=E203,W503"; then
        FAILURES=$((FAILURES + 1))
    fi
    echo ""
fi

# ========== 2. mypy: 类型检查 ==========
if check_command mypy; then
    if ! run_linter "mypy" \
        "mypy qbittorrent_monitor --ignore-missing-imports --show-error-codes"; then
        FAILURES=$((FAILURES + 1))
    fi
    echo ""
fi

# ========== 3. bandit: 安全检查 ==========
if check_command bandit; then
    if ! run_linter "bandit" \
        "bandit -r qbittorrent_monitor -c bandit.yaml -ll"; then
        FAILURES=$((FAILURES + 1))
    fi
    echo ""
fi

# ========== 4. pylint: 深度代码分析 (可选) ==========
if check_command pylint && [ "${RUN_PYLINT:-0}" = "1" ]; then
    if ! run_linter "pylint" \
        "pylint qbittorrent_monitor --max-line-length=100 --disable=C0103,C0114,C0115,C0116"; then
        FAILURES=$((FAILURES + 1))
    fi
    echo ""
fi

# ========== 总结 ==========
echo -e "${BLUE}===============================================${NC}"
echo -e "${BLUE}  检查结果汇总${NC}"
echo -e "${BLUE}===============================================${NC}"

if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✓ 所有检查通过!${NC}"
    echo ""
    echo -e "${GREEN}代码质量良好，可以提交。${NC}"
    exit 0
else
    echo -e "${RED}✗ 发现 $FAILURES 个检查未通过${NC}"
    echo ""
    echo -e "${YELLOW}请修复上述问题后再提交。${NC}"
    echo -e "${YELLOW}提示: 运行 ./scripts/format.sh 自动格式化代码${NC}"
    exit 1
fi
