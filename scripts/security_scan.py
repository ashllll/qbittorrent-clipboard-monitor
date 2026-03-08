#!/usr/bin/env python3
"""
依赖安全扫描脚本

扫描项目依赖中的已知安全漏洞。
"""

import subprocess
import sys
from pathlib import Path


def check_pip_audit():
    """检查 pip-audit 是否已安装"""
    try:
        import pip_audit
        return True
    except ImportError:
        return False


def install_pip_audit():
    """安装 pip-audit"""
    print("正在安装 pip-audit...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pip-audit"])


def run_pip_audit():
    """运行 pip-audit 扫描"""
    print("=" * 60)
    print("运行 pip-audit 安全扫描")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--desc"],
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print("错误信息:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"扫描失败: {e}")
        return False


def check_safety():
    """检查 safety 是否可用"""
    try:
        import safety
        return True
    except ImportError:
        return False


def run_safety_check():
    """运行 safety 检查"""
    print("\n" + "=" * 60)
    print("运行 safety 安全扫描")
    print("=" * 60)
    
    try:
        # 生成 requirements.txt
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True
        )
        
        requirements = result.stdout
        
        # 运行 safety
        result = subprocess.run(
            [sys.executable, "-m", "safety", "check", "--stdin"],
            input=requirements,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print("错误信息:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"扫描失败: {e}")
        return False


def main():
    """主函数"""
    print("qBittorrent Clipboard Monitor - 依赖安全扫描")
    print("=" * 60)
    
    # 检查 pip-audit
    if not check_pip_audit():
        print("pip-audit 未安装")
        response = input("是否安装 pip-audit? (y/n): ")
        if response.lower() == 'y':
            install_pip_audit()
        else:
            print("跳过 pip-audit 扫描")
    
    # 运行扫描
    results = []
    
    if check_pip_audit():
        results.append(("pip-audit", run_pip_audit()))
    
    if check_safety():
        results.append(("safety", run_safety_check()))
    
    # 打印结果摘要
    print("\n" + "=" * 60)
    print("扫描结果摘要")
    print("=" * 60)
    
    for tool, passed in results:
        status = "✅ 通过" if passed else "❌ 发现漏洞"
        print(f"{tool}: {status}")
    
    if not results:
        print("没有运行任何扫描工具")
        print("建议安装: pip install pip-audit safety")
    
    # 返回退出码
    return 0 if all(passed for _, passed in results) else 1


if __name__ == "__main__":
    sys.exit(main())
