#!/usr/bin/env python3
"""
Poetry验证脚本
检查Poetry安装是否成功以及依赖是否正确安装
"""

import subprocess
import sys
import os
from pathlib import Path

def check_poetry_installed():
    """检查Poetry是否已安装"""
    try:
        result = subprocess.run(
            ["poetry", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ Poetry已安装: {result.stdout.strip()}")
            return True
        else:
            print("❌ Poetry未安装或无法执行")
            return False
    except FileNotFoundError:
        print("❌ Poetry未安装（命令未找到）")
        return False

def check_pyproject_exists():
    """检查pyproject.toml文件是否存在"""
    pyproject_file = Path(__file__).parent.parent / "pyproject.toml"
    if pyproject_file.exists():
        print(f"✅ 找到pyproject.toml文件: {pyproject_file}")
        return True
    else:
        print(f"❌ 未找到pyproject.toml文件: {pyproject_file}")
        return False

def check_poetry_lock_exists():
    """检查poetry.lock文件是否存在"""
    lock_file = Path(__file__).parent.parent / "poetry.lock"
    if lock_file.exists():
        print(f"✅ 找到poetry.lock文件: {lock_file}")
        return True
    else:
        print(f"⚠️ 未找到poetry.lock文件（正常，但依赖未完全解析）")
        return False

def check_dependencies_installed():
    """检查项目依赖是否已安装"""
    try:
        result = subprocess.run(
            ["poetry", "check"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        if result.returncode == 0:
            print(f"✅ 项目配置有效")
            return True
        else:
            print(f"❌ 项目配置存在问题:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ 执行poetry check命令失败: {e}")
        return False

def check_key_dependencies():
    """检查关键依赖是否可用"""
    try:
        result = subprocess.run(
            ["poetry", "run", "python", "-c", "import aiohttp, pydantic, openai, tenacity; print('✅ 关键依赖可用')"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        if result.returncode == 0:
            print(result.stdout)
            return True
        else:
            print(f"❌ 关键依赖不可用:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ 执行依赖检查命令失败: {e}")
        return False

def install_dependencies():
    """尝试安装项目依赖"""
    try:
        print("尝试安装项目依赖...")
        subprocess.run(
            ["poetry", "install"],
            check=True,
            cwd=Path(__file__).parent.parent
        )
        print("✅ 依赖安装成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("🚀 Poetry环境验证")
    print("=" * 60)

    checks = [
        ("Poetry安装", check_poetry_installed),
        ("pyproject.toml存在", check_pyproject_exists),
        ("poetry.lock存在", check_poetry_lock_exists),
        ("项目配置有效", check_dependencies_installed),
        ("关键依赖可用", check_key_dependencies)
    ]

    results = []
    for name, check_func in checks:
        print(f"\n检查 {name}...")
        results.append(check_func())

    print("\n" + "=" * 60)
    print("📊 验证结果汇总")
    print("=" * 60)

    for i, (name, _) in enumerate(checks):
        status = "✅ 通过" if results[i] else "❌ 失败"
        print(f"{status} - {name}")

    # 如果依赖不可用，尝试安装
    if not results[-1]:
        print("\n尝试安装项目依赖...")
        if install_dependencies():
            print("依赖安装成功，重新检查...")
            check_key_dependencies()

    # 汇总结果
    all_passed = all(results)
    if all_passed:
        print("\n✅ 所有检查通过！Poetry环境已正确配置。")
        return 0
    else:
        print("\n❌ 某些检查未通过。请安装Poetry并运行'poetry install'。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
