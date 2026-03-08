#!/usr/bin/env python3
"""代码质量检查脚本

自动执行多项代码质量检查，包括：
- 代码风格检查（Black、isort）
- 类型检查（mypy）
- 静态分析（flake8、pylint）
- 安全扫描（bandit）
- 导入排序检查

使用方法:
    python scripts/code_quality_check.py [选项]

选项:
    --fix           自动修复可修复的问题
    --strict        启用严格模式（将警告视为错误）
    --skip-tests    跳过测试检查
    -v, --verbose   显示详细输出
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 需要检查的目录
SOURCE_DIRS = ["qbittorrent_monitor", "tests"]

# 颜色代码
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str) -> None:
    """打印标题"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")


def print_success(text: str) -> None:
    """打印成功消息"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str) -> None:
    """打印错误消息"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text: str) -> None:
    """打印警告消息"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def run_command(
    cmd: List[str],
    description: str,
    verbose: bool = False,
) -> Tuple[bool, str]:
    """运行命令并返回结果
    
    Args:
        cmd: 命令列表
        description: 命令描述
        verbose: 是否显示详细输出
    
    Returns:
        (是否成功, 输出内容)
    """
    if verbose:
        print(f"{Colors.OKCYAN}运行: {' '.join(cmd)}{Colors.ENDC}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr
        
        if result.returncode == 0:
            print_success(description)
            return True, output
        else:
            print_error(f"{description} (退出码: {result.returncode})")
            if verbose and output:
                print(output)
            return False, output
    
    except subprocess.TimeoutExpired:
        print_error(f"{description} (超时)")
        return False, ""
    except FileNotFoundError:
        print_error(f"{description} (命令未找到: {cmd[0]})")
        return False, ""


def check_black(fix: bool = False, verbose: bool = False) -> bool:
    """检查代码格式化（Black）
    
    Args:
        fix: 是否自动修复
        verbose: 是否显示详细输出
    
    Returns:
        是否通过检查
    """
    print_header("1. 代码格式化检查 (Black)")
    
    cmd = ["black", "--check", "--diff"] + SOURCE_DIRS
    
    if fix:
        cmd = ["black"] + SOURCE_DIRS
        print(f"{Colors.OKCYAN}正在自动修复代码格式...{Colors.ENDC}")
    
    success, output = run_command(cmd, "代码格式化", verbose)
    
    if not success and not fix and "would reformat" in output:
        print_warning("运行 `python scripts/code_quality_check.py --fix` 自动修复")
    
    return success


def check_isort(fix: bool = False, verbose: bool = False) -> bool:
    """检查导入排序（isort）
    
    Args:
        fix: 是否自动修复
        verbose: 是否显示详细输出
    
    Returns:
        是否通过检查
    """
    print_header("2. 导入排序检查 (isort)")
    
    cmd = ["isort", "--check-only", "--diff"] + SOURCE_DIRS
    
    if fix:
        cmd = ["isort"] + SOURCE_DIRS
        print(f"{Colors.OKCYAN}正在自动修复导入排序...{Colors.ENDC}")
    
    success, output = run_command(cmd, "导入排序", verbose)
    
    if not success and not fix:
        print_warning("运行 `python scripts/code_quality_check.py --fix` 自动修复")
    
    return success


def check_mypy(verbose: bool = False) -> bool:
    """检查类型注解（mypy）
    
    Args:
        verbose: 是否显示详细输出
    
    Returns:
        是否通过检查
    """
    print_header("3. 类型检查 (mypy)")
    
    cmd = ["mypy", "qbittorrent_monitor"]
    success, output = run_command(cmd, "类型检查", verbose)
    
    if not success and verbose:
        print(output)
    
    return success


def check_flake8(verbose: bool = False) -> bool:
    """检查代码风格（flake8）
    
    Args:
        verbose: 是否显示详细输出
    
    Returns:
        是否通过检查
    """
    print_header("4. 代码风格检查 (flake8)")
    
    cmd = ["flake8"] + SOURCE_DIRS
    success, output = run_command(cmd, "代码风格", verbose)
    
    if not success and verbose:
        print(output)
    
    return success


def check_bandit(verbose: bool = False) -> bool:
    """安全扫描（bandit）
    
    Args:
        verbose: 是否显示详细输出
    
    Returns:
        是否通过检查
    """
    print_header("5. 安全扫描 (bandit)")
    
    cmd = [
        "bandit",
        "-r",
        "qbittorrent_monitor",
        "-f", "json",
        "-o", "/dev/null" if sys.platform != "win32" else "NUL",
    ]
    
    # 同时获取详细输出
    cmd_verbose = ["bandit", "-r", "qbittorrent_monitor"]
    success, output = run_command(cmd_verbose, "安全扫描", verbose)
    
    return success


def check_pydocstyle(verbose: bool = False) -> bool:
    """检查文档字符串（pydocstyle）
    
    Args:
        verbose: 是否显示详细输出
    
    Returns:
        是否通过检查
    """
    print_header("6. 文档字符串检查 (pydocstyle)")
    
    cmd = ["pydocstyle", "qbittorrent_monitor"]
    success, output = run_command(cmd, "文档字符串", verbose)
    
    # pydocstyle 返回非零退出码表示有警告，但这不一定是错误
    if not success and verbose:
        print(output)
    
    return success


def check_imports(verbose: bool = False) -> bool:
    """检查导入规范
    
    检查是否遵循项目导入规范：
    - 标准库导入在前
    - 第三方库导入次之
    - 本地导入最后
    
    Args:
        verbose: 是否显示详细输出
    
    Returns:
        是否通过检查
    """
    print_header("7. 导入规范检查")
    
    issues = []
    
    for dir_name in SOURCE_DIRS:
        dir_path = PROJECT_ROOT / dir_name
        if not dir_path.exists():
            continue
        
        for py_file in dir_path.rglob("*.py"):
            if py_file.name.startswith("."):
                continue
            
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 检查是否有 __future__ 导入
            if "from __future__ import" not in content and content.strip():
                # 排除空文件和 __init__.py
                if py_file.name != "__init__.py":
                    issues.append(f"{py_file}: 缺少 __future__ 导入")
            
            # 检查相对导入
            if "from ." in content and py_file.name != "__init__.py":
                # 相对导入在项目中是可以的，但这里只是检查
                pass
    
    if issues:
        print_error("导入规范检查")
        for issue in issues[:10]:  # 只显示前10个
            print(f"  - {issue}")
        if len(issues) > 10:
            print(f"  ... 还有 {len(issues) - 10} 个问题")
        return False
    
    print_success("导入规范检查")
    return True


def check_tests(verbose: bool = False) -> bool:
    """运行单元测试
    
    Args:
        verbose: 是否显示详细输出
    
    Returns:
        是否通过检查
    """
    print_header("8. 单元测试")
    
    cmd = ["pytest", "tests/", "-v", "--tb=short"]
    
    if not verbose:
        cmd.extend(["-q"])
    
    success, output = run_command(cmd, "单元测试", verbose)
    
    if not success and verbose:
        print(output)
    
    return success


def main() -> int:
    """主函数
    
    Returns:
        退出码（0 表示成功）
    """
    parser = argparse.ArgumentParser(
        description="代码质量检查工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/code_quality_check.py           # 运行所有检查
    python scripts/code_quality_check.py --fix     # 自动修复问题
    python scripts/code_quality_check.py -v        # 显示详细输出
        """,
    )
    
    parser.add_argument(
        "--fix",
        action="store_true",
        help="自动修复可修复的问题",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="将警告视为错误",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="跳过测试检查",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细输出",
    )
    
    args = parser.parse_args()
    
    print_header("代码质量检查工具")
    print(f"项目目录: {PROJECT_ROOT}")
    print(f"检查目录: {', '.join(SOURCE_DIRS)}")
    
    results = []
    
    # 1. 代码格式化检查
    results.append(("Black", check_black(fix=args.fix, verbose=args.verbose)))
    
    # 2. 导入排序检查
    results.append(("isort", check_isort(fix=args.fix, verbose=args.verbose)))
    
    # 3. 类型检查
    results.append(("mypy", check_mypy(verbose=args.verbose)))
    
    # 4. 代码风格检查
    results.append(("flake8", check_flake8(verbose=args.verbose)))
    
    # 5. 安全扫描
    results.append(("bandit", check_bandit(verbose=args.verbose)))
    
    # 6. 文档字符串检查（严格模式下视为错误）
    doc_success = check_pydocstyle(verbose=args.verbose)
    if args.strict:
        results.append(("pydocstyle", doc_success))
    
    # 7. 导入规范检查
    results.append(("imports", check_imports(verbose=args.verbose)))
    
    # 8. 单元测试
    if not args.skip_tests:
        results.append(("pytest", check_tests(verbose=args.verbose)))
    
    # 汇总结果
    print_header("检查结果汇总")
    
    passed = 0
    failed = 0
    
    for name, success in results:
        if success:
            print_success(f"{name:20s} 通过")
            passed += 1
        else:
            print_error(f"{name:20s} 失败")
            failed += 1
    
    print(f"\n{Colors.BOLD}总计: {passed} 通过, {failed} 失败{Colors.ENDC}")
    
    if failed > 0:
        print(f"\n{Colors.FAIL}代码质量检查未通过，请修复上述问题。{Colors.ENDC}")
        return 1
    
    print(f"\n{Colors.OKGREEN}所有检查通过！代码质量良好。{Colors.ENDC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
