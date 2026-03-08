#!/bin/bash
#
# pre-commit-check.sh - 自定义 pre-commit 检查脚本
#
# 此脚本用于在 pre-commit 钩子中执行项目特定的检查
# 包括：
# - 检查版本号一致性
# - 检查敏感信息泄露
# - 检查文档更新
# - 检查测试覆盖率阈值
#

set -e

echo "========================================"
echo "Running custom pre-commit checks..."
echo "========================================"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 计数器
ERRORS=0
WARNINGS=0

# ==========================================
# 辅助函数
# ==========================================

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
    ((ERRORS++))
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARNINGS++))
}

# ==========================================
# 检查 1: Python 语法检查
# ==========================================
check_python_syntax() {
    echo ""
    echo "Checking Python syntax..."
    
    local python_files=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)
    
    if [ -z "$python_files" ]; then
        print_success "No Python files to check"
        return 0
    fi
    
    local has_error=0
    for file in $python_files; do
        if [ -f "$file" ]; then
            if ! python -m py_compile "$file" 2>/dev/null; then
                print_error "Syntax error in $file"
                has_error=1
            fi
        fi
    done
    
    if [ $has_error -eq 0 ]; then
        print_success "All Python files have valid syntax"
    fi
}

# ==========================================
# 检查 2: 敏感信息泄露检查
# ==========================================
check_sensitive_info() {
    echo ""
    echo "Checking for sensitive information..."
    
    local patterns=(
        'password\s*=\s*["\'][^"\']+["\']'
        'api_key\s*=\s*["\'][^"\']+["\']'
        'secret\s*=\s*["\'][^"\']+["\']'
        'token\s*=\s*["\'][^"\']+["\']'
        'sk-[a-zA-Z0-9]{20,}'
        'AKIA[0-9A-Z]{16}'
        'ghp_[a-zA-Z0-9]{36}'
    )
    
    local staged_files=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(py|json|yaml|yml|env|sh)$' || true)
    
    if [ -z "$staged_files" ]; then
        print_success "No files to check for sensitive info"
        return 0
    fi
    
    local has_issue=0
    for file in $staged_files; do
        if [ -f "$file" ]; then
            for pattern in "${patterns[@]}"; do
                if grep -iEn "$pattern" "$file" 2>/dev/null | grep -v "example\|template\|placeholder\|your-" > /dev/null; then
                    print_warning "Possible sensitive info in $file matching pattern: $pattern"
                    has_issue=1
                fi
            done
        fi
    done
    
    if [ $has_issue -eq 0 ]; then
        print_success "No obvious sensitive information detected"
    fi
}

# ==========================================
# 检查 3: 配置文件有效性
# ==========================================
check_config_files() {
    echo ""
    echo "Checking configuration files..."
    
    # 检查 JSON 文件
    local json_files=$(git diff --cached --name-only --diff-filter=ACM | grep '\.json$' || true)
    for file in $json_files; do
        if [ -f "$file" ]; then
            if ! python -c "import json; json.load(open('$file'))" 2>/dev/null; then
                print_error "Invalid JSON: $file"
            else
                print_success "Valid JSON: $file"
            fi
        fi
    done
    
    # 检查 YAML 文件
    local yaml_files=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(yaml|yml)$' || true)
    for file in $yaml_files; do
        if [ -f "$file" ]; then
            if ! python -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null; then
                print_error "Invalid YAML: $file"
            else
                print_success "Valid YAML: $file"
            fi
        fi
    done
}

# ==========================================
# 检查 4: 检查是否包含调试代码
# ==========================================
check_debug_code() {
    echo ""
    echo "Checking for debug code..."
    
    local debug_patterns=(
        'pdb\.set_trace\(\)'
        'breakpoint\(\)'
        'import pdb'
        'console\.log\('
        'print\("debug'
        'print\(\[debug'
        '# DEBUG'
        'TODO:'
        'FIXME:'
        'XXX:'
    )
    
    local python_files=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)
    
    if [ -z "$python_files" ]; then
        print_success "No Python files to check"
        return 0
    fi
    
    local found_debug=0
    for file in $python_files; do
        if [ -f "$file" ]; then
            for pattern in "${debug_patterns[@]}"; do
                if grep -n "$pattern" "$file" 2>/dev/null > /dev/null; then
                    print_warning "Found debug marker in $file: $pattern"
                    found_debug=1
                fi
            done
        fi
    done
    
    if [ $found_debug -eq 0 ]; then
        print_success "No obvious debug code found"
    fi
}

# ==========================================
# 检查 5: 检查测试文件是否更新
# ==========================================
check_tests_updated() {
    echo ""
    echo "Checking if tests are updated..."
    
    local python_files=$(git diff --cached --name-only --diff-filter=ACM | grep '^qbittorrent_monitor/.*\.py$' || true)
    local test_files=$(git diff --cached --name-only --diff-filter=ACM | grep '^tests/.*\.py$' || true)
    
    if [ -n "$python_files" ] && [ -z "$test_files" ]; then
        print_warning "Source files changed but no test files updated"
        echo "  Changed source files:"
        for f in $python_files; do
            echo "    - $f"
        done
        echo "  Consider adding/updating tests for these changes"
    else
        print_success "Tests check passed"
    fi
}

# ==========================================
# 检查 6: 检查文档是否同步
# ==========================================
check_documentation() {
    echo ""
    echo "Checking documentation..."
    
    # 检查 README 是否存在
    if [ ! -f "README.md" ]; then
        print_error "README.md not found"
        return 1
    fi
    
    # 检查 README 是否包含关键章节
    local required_sections=("安装\|部署" "配置\|使用" "特性\|功能")
    for section in "${required_sections[@]}"; do
        if ! grep -q "$section" README.md 2>/dev/null; then
            print_warning "README.md may be missing section: $section"
        fi
    done
    
    # 检查是否有文档更新
    local doc_files=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(md|rst)$' || true)
    local src_files=$(git diff --cached --name-only --diff-filter=ACM | grep '^qbittorrent_monitor/.*\.py$' || true)
    
    if [ -n "$src_files" ] && [ -z "$doc_files" ]; then
        print_warning "Source code changed but no documentation updated"
    fi
    
    print_success "Documentation check completed"
}

# ==========================================
# 检查 7: 检查文件权限
# ==========================================
check_file_permissions() {
    echo ""
    echo "Checking file permissions..."
    
    # 检查脚本文件是否可执行
    local script_files=$(find scripts -type f -name "*.sh" 2>/dev/null || true)
    for file in $script_files; do
        if [ ! -x "$file" ]; then
            print_warning "Script not executable: $file"
            echo "    Run: chmod +x $file"
        fi
    done
    
    print_success "File permissions check completed"
}

# ==========================================
# 检查 8: 检查导入顺序
# ==========================================
check_import_order() {
    echo ""
    echo "Checking import order..."
    
    local python_files=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)
    
    if [ -z "$python_files" ]; then
        print_success "No Python files to check"
        return 0
    fi
    
    # 简单的导入顺序检查
    local has_issue=0
    for file in $python_files; do
        if [ -f "$file" ]; then
            # 检查是否有重复的导入
            if grep -E '^import |^from ' "$file" 2>/dev/null | sort | uniq -d | grep -q .; then
                print_warning "Possible duplicate imports in $file"
                has_issue=1
            fi
        fi
    done
    
    if [ $has_issue -eq 0 ]; then
        print_success "Import order check passed"
    fi
}

# ==========================================
# 主函数
# ==========================================
main() {
    echo ""
    echo "Project: qbittorrent-clipboard-monitor"
    echo "========================================"
    
    # 运行所有检查
    check_python_syntax
    check_sensitive_info
    check_config_files
    check_debug_code
    check_tests_updated
    check_documentation
    check_file_permissions
    check_import_order
    
    # 输出总结
    echo ""
    echo "========================================"
    echo "Summary:"
    echo "========================================"
    
    if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
        echo -e "${GREEN}All checks passed! ✓${NC}"
        exit 0
    elif [ $ERRORS -eq 0 ]; then
        echo -e "${YELLOW}Checks completed with $WARNINGS warning(s) ⚠${NC}"
        echo "Warnings don't block the commit, but please review them."
        exit 0
    else
        echo -e "${RED}Checks failed with $ERRORS error(s) and $WARNINGS warning(s) ✗${NC}"
        exit 1
    fi
}

# 运行主函数
main "$@"
