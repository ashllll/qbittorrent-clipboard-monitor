#!/bin/bash

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的信息
print_info() {
    echo -e "${BLUE}🔍 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${BLUE}===========================================${NC}"
    echo -e "${BLUE}🚀 QBittorrent智能下载助手启动脚本${NC}"
    echo -e "${BLUE}===========================================${NC}"
}

# 设置变量
VENV_DIR="venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 打印标题
print_header

# 检查Python是否安装
print_info "检查Python环境..."
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        print_error "未找到Python，请先安装Python 3.8+"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

# 显示Python版本
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
print_success "找到Python $PYTHON_VERSION"

# 检查Python版本是否符合要求
PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    print_error "Python版本过低，需要Python 3.8+，当前版本: $PYTHON_VERSION"
    exit 1
fi

# 进入脚本目录
cd "$SCRIPT_DIR"

# 检查虚拟环境是否存在
if [ ! -d "$VENV_DIR" ]; then
    print_info "创建虚拟环境..."
    $PYTHON_CMD -m venv $VENV_DIR
    if [ $? -ne 0 ]; then
        print_error "创建虚拟环境失败"
        exit 1
    fi
    print_success "虚拟环境创建成功"
else
    print_success "虚拟环境已存在"
fi

# 激活虚拟环境
print_info "激活虚拟环境..."
source "$VENV_DIR/bin/activate"
if [ $? -ne 0 ]; then
    print_error "激活虚拟环境失败"
    exit 1
fi

# 升级pip
print_info "升级pip..."
python -m pip install --upgrade pip --quiet

# 检查和安装依赖
print_info "检查和安装依赖包..."
if [ -f "requirements.txt" ]; then
    print_info "读取requirements.txt..."
    python -m pip install -r requirements.txt --quiet
    if [ $? -ne 0 ]; then
        print_error "安装依赖失败"
        print_info "正在详细安装..."
        python -m pip install -r requirements.txt
        exit 1
    fi
    print_success "依赖安装完成"
else
    print_warning "未找到requirements.txt文件"
    print_info "安装基础依赖..."
    python -m pip install aiohttp pyperclip --quiet
fi

# 检查配置文件
print_info "检查配置文件..."
if [ ! -f "qbittorrent_monitor/config.json" ]; then
    print_error "配置文件不存在: qbittorrent_monitor/config.json"
    print_warning "请确保配置文件存在并配置正确"
    exit 1
fi
print_success "配置文件检查完成"

# 显示启动信息
echo
echo -e "${BLUE}===========================================${NC}"
echo -e "${BLUE}🎯 准备启动程序...${NC}"
echo -e "${BLUE}📁 虚拟环境: $VENV_DIR${NC}"
echo -e "${BLUE}📄 配置文件: qbittorrent_monitor/config.json${NC}"
echo -e "${BLUE}🚀 启动方式: python start.py${NC}"
echo -e "${BLUE}===========================================${NC}"
echo

# 启动程序
print_info "启动QBittorrent智能下载助手..."
python start.py

# 程序结束后的提示
echo
print_info "程序已退出" 