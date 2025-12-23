#!/bin/bash

# 覆盖率检查脚本
# 用于在本地检查代码覆盖率，确保代码提交前符合覆盖率要求

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_message() {
    echo -e "${2:-$NC}$1${NC}"
}

print_header() {
    echo ""
    print_message "=======================================" "$BLUE"
    print_message "$1" "$BLUE"
    print_message "=======================================" "$BLUE"
    echo ""
}

print_success() {
    print_message "✅ $1" "$GREEN"
}

print_warning() {
    print_message "⚠️ $1" "$YELLOW"
}

print_error() {
    print_message "❌ $1" "$RED"
}

# 检查依赖
check_dependencies() {
    print_header "检查依赖"
    
    if ! command -v poetry &> /dev/null; then
        print_error "Poetry 未安装，请先安装 Poetry"
        exit 1
    fi
    print_success "Poetry 已安装"
    
    if ! poetry show --tree | grep -q "pytest-cov"; then
        print_error "pytest-cov 未安装，请运行: poetry add --group dev pytest-cov"
        exit 1
    fi
    print_success "pytest-cov 已安装"
}

# 运行测试并生成覆盖率报告
run_tests() {
    print_header "运行测试并生成覆盖率报告"
    
    print_message "运行单元测试..." "$BLUE"
    poetry run pytest tests/unit/ \
        --cov=qbittorrent_monitor \
        --cov-report=term-missing \
        --cov-report=html \
        --cov-report=xml \
        --cov-fail-under=85 \
        -v || {
        print_error "单元测试失败或覆盖率低于85%"
        return 1
    }
    
    print_message "运行集成测试..." "$BLUE"
    poetry run pytest tests/integration/ \
        --cov=qbittorrent_monitor \
        --cov-report=term-missing \
        --cov-report=html \
        --cov-report=xml \
        --cov-fail-under=70 \
        -v || {
        print_error "集成测试失败或覆盖率低于70%"
        return 1
    }
    
    return 0
}

# 检查各模块覆盖率
check_module_coverage() {
    print_header "检查各模块覆盖率"
    
    local failed=0
    
    # 检查核心模块
    print_message "检查 AI 分类器覆盖率..." "$BLUE"
    if poetry run coverage report --include="qbittorrent_monitor/ai_classifier.py" --fail-under=90; then
        print_success "AI 分类器覆盖率符合要求 (>=90%)"
    else
        print_error "AI 分类器覆盖率低于 90%"
        failed=1
    fi
    
    print_message "检查 qBittorrent 客户端覆盖率..." "$BLUE"
    if poetry run coverage report --include="qbittorrent_monitor/qbittorrent_client.py" --fail-under=90; then
        print_success "qBittorrent 客户端覆盖率符合要求 (>=90%)"
    else
        print_error "qBittorrent 客户端覆盖率低于 90%"
        failed=1
    fi
    
    print_message "检查配置模块覆盖率..." "$BLUE"
    if poetry run coverage report --include="qbittorrent_monitor/config.py" --fail-under=95; then
        print_success "配置模块覆盖率符合要求 (>=95%)"
    else
        print_error "配置模块覆盖率低于 95%"
        failed=1
    fi
    
    print_message "检查异常模块覆盖率..." "$BLUE"
    if poetry run coverage report --include="qbittorrent_monitor/exceptions.py" --fail-under=100; then
        print_success "异常模块覆盖率符合要求 (>=100%)"
    else
        print_error "异常模块覆盖率低于 100%"
        failed=1
    fi
    
    print_message "检查网页爬虫覆盖率..." "$BLUE"
    if poetry run coverage report --include="qbittorrent_monitor/web_crawler.py" --fail-under=85; then
        print_success "网页爬虫覆盖率符合要求 (>=85%)"
    else
        print_error "网页爬虫覆盖率低于 85%"
        failed=1
    fi
    
    print_message "检查剪贴板监控器覆盖率..." "$BLUE"
    if poetry run coverage report --include="qbittorrent_monitor/clipboard_monitor.py" --fail-under=85; then
        print_success "剪贴板监控器覆盖率符合要求 (>=85%)"
    else
        print_error "剪贴板监控器覆盖率低于 85%"
        failed=1
    fi
    
    print_message "检查弹性设计模块覆盖率..." "$BLUE"
    if poetry run coverage report --include="qbittorrent_monitor/resilience.py" --fail-under=95; then
        print_success "弹性设计模块覆盖率符合要求 (>=95%)"
    else
        print_error "弹性设计模块覆盖率低于 95%"
        failed=1
    fi
    
    print_message "检查工具函数覆盖率..." "$BLUE"
    if poetry run coverage report --include="qbittorrent_monitor/utils.py" --fail-under=90; then
        print_success "工具函数覆盖率符合要求 (>=90%)"
    else
        print_error "工具函数覆盖率低于 90%"
        failed=1
    fi
    
    return $failed
}

# 生成覆盖率报告
generate_coverage_report() {
    print_header "生成覆盖率报告"
    
    # 生成 HTML 报告
    poetry run coverage html
    print_success "HTML 覆盖率报告已生成: htmlcov/index.html"
    
    # 生成 XML 报告
    poetry run coverage xml
    print_success "XML 覆盖率报告已生成: coverage.xml"
    
    # 显示覆盖率统计
    print_header "覆盖率统计"
    poetry run coverage report --show-missing
}

# 主函数
main() {
    print_header "开始覆盖率检查"
    
    # 检查依赖
    check_dependencies
    
    # 运行测试并生成覆盖率报告
    if ! run_tests; then
        print_error "测试失败，请修复测试和覆盖率问题后再试"
        exit 1
    fi
    
    # 检查各模块覆盖率
    if ! check_module_coverage; then
        print_error "部分模块覆盖率不符合要求，请添加更多测试"
        exit 1
    fi
    
    # 生成覆盖率报告
    generate_coverage_report
    
    print_header "覆盖率检查完成"
    print_success "所有覆盖率要求都已满足！"
    
    # 显示下一步操作建议
    echo ""
    print_message "下一步操作建议:" "$BLUE"
    echo "1. 查看详细覆盖率报告: open htmlcov/index.html"
    echo "2. 运行特定模块测试: poetry run pytest tests/unit/test_ai_classifier.py -v"
    echo "3. 运行集成测试: poetry run pytest tests/integration/ -v"
    echo "4. 提交代码前确保所有测试通过: poetry run pytest"
}

# 处理命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --quick|-q)
            print_message "快速模式：只运行核心模块测试" "$YELLOW"
            poetry run pytest tests/unit/test_ai_classifier.py tests/unit/test_qbittorrent_client.py tests/unit/test_web_crawler.py \
                --cov=qbittorrent_monitor \
                --cov-report=term-missing \
                --cov-fail-under=90 \
                -v || {
                print_error "快速测试失败"
                exit 1
            }
            shift
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo "选项:"
            echo "  --quick, -q     快速模式：只运行核心模块测试"
            echo "  --help, -h      显示帮助信息"
            exit 0
            ;;
        *)
            print_error "未知选项: $1"
            echo "使用 --help 查看帮助信息"
            exit 1
            ;;
    esac
done

# 运行主函数
main
