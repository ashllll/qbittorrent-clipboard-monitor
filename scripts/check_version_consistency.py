#!/usr/bin/env python3
"""
版本一致性检查脚本

检查项目中是否存在硬编码的版本号，确保版本信息统一管理
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict

# 需要排除的文件和目录
EXCLUDE_PATTERNS = [
    "__version__.py",
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    ".git",
    ".svn",
    "__pycache__",
    "*.pyc",
    "*.log",
    ".DS_Store",
    ".idea",
    ".vscode",
    ".agent",
    "node_modules",
    "workspace",
    "browser/user_data*",
    "browser/sessions",
    "mcp_downloaded",
    "debug",
    "log",
    "pyproject.toml",
    "external_api",
    "pyarmor_runtime_000000",
    "uv.lock",
]

# 允许的版本号模式（主要在__version__.py中）
ALLOWED_VERSION_PATTERNS = [
    r'__version__\s*=\s*["\'](\d+\.\d+\.\d+)["\']',
    r'__version_info__\s*=\s*\((\d+,\s*\d+,\s*\d+)\)',
]

# 禁止的硬编码版本号模式
FORBIDDEN_PATTERNS = [
    r'version\s*=\s*["\'](\d+\.\d+\.\d+)["\']',  # 字典赋值
    r'["\'](\d+\.\d+\.\d+)["\']\s*(?:#.*)?$',  # 字符串形式的版本号
    r'v(\d+\.\d+\.\d+)',  # v前缀的版本号
    r'\(v(\d+\.\d+\.\d+)\)',  # 括号中的版本号
]


def should_exclude(file_path: Path) -> bool:
    """检查文件是否应该被排除"""
    file_str = str(file_path)
    for pattern in EXCLUDE_PATTERNS:
        if pattern in file_str:
            return True
    return False


def check_file_for_hardcoded_versions(file_path: Path) -> List[Tuple[int, str, str]]:
    """检查文件中的硬编码版本号"""
    violations = []

    # 检查是否为允许的文件
    if file_path.name == "__version__.py":
        return violations  # 允许此文件包含版本信息

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, 1):
            # 跳过注释行
            if line.strip().startswith('#'):
                continue

            # 检查是否包含允许的模式
            for pattern in ALLOWED_VERSION_PATTERNS:
                if re.search(pattern, line):
                    continue

            # 检查是否包含禁止的模式
            for pattern in FORBIDDEN_PATTERNS:
                matches = re.finditer(pattern, line)
                for match in matches:
                    # 额外检查：如果是注释的一部分，跳过
                    comment_pos = line.find('#')
                    if comment_pos != -1 and match.start() > comment_pos:
                        continue

                    violations.append((
                        line_num,
                        line.strip(),
                        match.group(0)
                    ))

    except Exception as e:
        print(f"[警告] 无法读取文件 {file_path}: {e}")

    return violations


def find_version_violations(root_dir: Path) -> Dict[str, List[Tuple[int, str, str]]]:
    """查找所有版本号违规"""
    violations = {}

    # 遍历项目目录
    for file_path in root_dir.rglob('*.py'):
        if should_exclude(file_path):
            continue

        file_violations = check_file_for_hardcoded_versions(file_path)
        if file_violations:
            violations[str(file_path)] = file_violations

    return violations


def check_version_consistency():
    """检查版本一致性"""
    print("=" * 70)
    print("[检查] qBittorrent 剪贴板监控项目 - 版本一致性检查")
    print("=" * 70)
    print()

    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    print(f"[目录] 项目根目录: {project_root}")
    print()

    # 检查版本管理模块是否存在
    version_file = project_root / "qbittorrent_monitor" / "__version__.py"
    if not version_file.exists():
        print("[错误] 未找到 __version__.py 文件！")
        print("       请先创建中央版本管理模块。")
        return False

    print(f"[OK] 找到版本管理模块: {version_file}")
    print()

    # 检查版本信息是否正确
    try:
        sys.path.insert(0, str(project_root / "qbittorrent_monitor"))
        import __version__

        print(f"[信息] 当前版本: {__version__.__version__}")
        print(f"[信息] 版本信息: {__version__.__version_info__}")
        print()
    except Exception as e:
        print(f"[错误] 无法导入版本模块: {e}")
        return False

    # 查找硬编码版本号
    print("[检查] 扫描硬编码版本号...")
    violations = find_version_violations(project_root)

    if not violations:
        print("[OK] 未发现硬编码版本号违规！")
        print()
        print("=" * 70)
        print("[OK] 版本一致性检查通过！")
        print("=" * 70)
        return True

    # 报告违规
    print(f"[错误] 发现 {len(violations)} 个文件包含硬编码版本号:")
    print()

    total_violations = 0
    for file_path, file_violations in violations.items():
        print(f"[文件] {file_path}")
        for line_num, line_content, matched_text in file_violations:
            print(f"       行 {line_num}: {line_content}")
            print(f"       [警告] 违规: {matched_text}")
            total_violations += 1
        print()

    print("=" * 70)
    print(f"[错误] 共发现 {total_violations} 处硬编码版本号违规！")
    print("=" * 70)
    print()
    print("[建议] 修复建议:")
    print("   1. 在 qbittorrent_monitor/__version__.py 中定义版本信息")
    print("   2. 使用 'from .__version__ import __version__' 导入版本")
    print("   3. 使用变量而不是硬编码字符串")
    print()

    return False


if __name__ == "__main__":
    success = check_version_consistency()
    sys.exit(0 if success else 1)
