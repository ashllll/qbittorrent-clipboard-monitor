#!/bin/bash
# Pre-commit hooks安装脚本

set -e

echo "================================================"
echo "  qBittorrent 剪贴板监控项目 - Pre-commit Hooks安装"
echo "================================================"
echo

# 检查Python版本
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then
    echo "✅ Python版本检查通过: $python_version"
else
    echo "❌ Python版本过低: $python_version (需要 >= $required_version)"
    exit 1
fi

# 检查是否在git仓库中
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ 错误: 当前目录不是Git仓库"
    echo "   请在项目根目录运行此脚本"
    exit 1
fi

# 安装pre-commit
echo
echo "📦 安装pre-commit..."
if command -v pip &> /dev/null; then
    pip install pre-commit
elif command -v pip3 &> /dev/null; then
    pip3 install pre-commit
else
    echo "❌ 错误: 未找到pip命令"
    exit 1
fi

# 安装hooks
echo
echo "🔧 安装Git hooks..."
pre-commit install

# 安装commit-msg hook
echo
echo "📝 安装commit-msg hook..."
pre-commit install --hook-type commit-msg

# 运行一次检查（可选）
echo
read -p "是否现在运行一次完整检查? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo
    echo "🔍 运行完整检查..."
    pre-commit run --all-files
else
    echo
    echo "⏭️  跳过检查，下次提交时自动运行"
fi

echo
echo "================================================"
echo "  ✅ Pre-commit hooks安装完成！"
echo "================================================"
echo
echo "📋 使用说明:"
echo "   - 每次提交时自动运行代码质量检查"
echo "   - 如需手动运行: pre-commit run --all-files"
echo "   - 如需跳过检查: git commit --no-verify"
echo "   - 如需更新hooks: pre-commit autoupdate"
echo
echo "🔧 配置文件: .pre-commit-config.yaml"
echo "📚 更多信息: https://pre-commit.com/"
echo
