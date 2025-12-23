#!/usr/bin/env python3
"""
代码重复分析脚本

分析项目中存在的重复模块，提供详细的合并建议
"""

import os
import ast
import difflib
from pathlib import Path
from typing import List, Dict, Tuple


def analyze_file_functions(file_path: Path) -> Dict:
    """分析文件中的函数和类"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)

        functions = []
        classes = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    'name': node.name,
                    'line': node.lineno,
                    'args': [arg.arg for arg in node.args.args]
                })
            elif isinstance(node, ast.ClassDef):
                classes.append({
                    'name': node.name,
                    'line': node.lineno,
                    'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                })
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                else:
                    imports.append(node.module or '')

        return {
            'functions': functions,
            'classes': classes,
            'imports': imports,
            'total_lines': len(content.splitlines())
        }
    except Exception as e:
        return {'error': str(e)}


def compare_modules(base_file: Path, enhanced_file: Path) -> Dict:
    """比较两个模块的差异"""
    base_info = analyze_file_functions(base_file)
    enhanced_info = analyze_file_functions(enhanced_file)

    if 'error' in base_info or 'error' in enhanced_info:
        return {'error': base_info.get('error') or enhanced_info.get('error')}

    # 计算重复度
    base_functions = {f['name'] for f in base_info['functions']}
    enhanced_functions = {f['name'] for f in enhanced_info['functions']}

    common_functions = base_functions & enhanced_functions
    unique_to_base = base_functions - enhanced_functions
    unique_to_enhanced = enhanced_functions - base_functions

    # 计算相似度
    with open(base_file, 'r', encoding='utf-8') as f:
        base_content = f.readlines()
    with open(enhanced_file, 'r', encoding='utf-8') as f:
        enhanced_content = f.readlines()

    similarity = difflib.SequenceMatcher(None, base_content, enhanced_content).ratio()

    return {
        'base_file': str(base_file),
        'enhanced_file': str(enhanced_file),
        'base_info': base_info,
        'enhanced_info': enhanced_info,
        'common_functions': list(common_functions),
        'unique_to_base': list(unique_to_base),
        'unique_to_enhanced': list(unique_to_enhanced),
        'similarity': similarity,
        'recommendation': get_recommendation(base_info, enhanced_info, similarity)
    }


def get_recommendation(base_info: Dict, enhanced_info: Dict, similarity: float) -> str:
    """基于分析结果给出合并建议"""
    if similarity > 0.8:
        if enhanced_info['total_lines'] < base_info['total_lines']:
            return "建议保留 enhanced 版本，移除基础版本"
        else:
            return "建议保留基础版本，移除 enhanced 版本"
    elif similarity > 0.5:
        return "建议合并两个版本，保留所有功能"
    else:
        return "两个版本差异较大，需要手动分析"


def generate_merge_plan(pairs: List[Tuple[str, str]]) -> str:
    """生成合并计划"""
    plan = """
# 代码重复合并计划

## 合并策略
- 保留 enhanced 版本（通常是优化后的版本）
- 将基础版本中的独有功能迁移到 enhanced 版本
- 更新所有导入引用
- 删除基础版本

## 详细计划

"""
    for i, (base, enhanced) in enumerate(pairs, 1):
        base_name = Path(base).stem
        enhanced_name = Path(enhanced).stem

        plan += f"""
### {i}. {base_name} vs {enhanced_name}

**文件**:
- 基础版本: `{base}`
- 增强版本: `{enhanced}`

**合并步骤**:
1. 分析两个版本的差异
2. 将基础版本独有功能迁移到增强版本
3. 更新测试文件导入
4. 删除基础版本
5. 验证合并后功能正常

"""

    return plan


def main():
    """主函数"""
    print("=" * 70)
    print("[分析] qBittorrent 剪贴板监控项目 - 代码重复分析")
    print("=" * 70)
    print()

    project_root = Path(__file__).parent.parent
    monitor_dir = project_root / "qbittorrent_monitor"

    # 定义重复模块对
    duplicate_pairs = [
        (monitor_dir / "config.py", monitor_dir / "config_enhanced.py"),
        (monitor_dir / "clipboard_monitor.py", monitor_dir / "clipboard_monitor_enhanced.py"),
        (monitor_dir / "qbittorrent_client.py", monitor_dir / "qbittorrent_client_enhanced.py"),
        (monitor_dir / "exceptions.py", monitor_dir / "exceptions_enhanced.py"),
        (monitor_dir / "web_crawler.py", monitor_dir / "web_crawler_enhanced.py"),
    ]

    results = []

    for base_file, enhanced_file in duplicate_pairs:
        if not base_file.exists() or not enhanced_file.exists():
            print(f"[跳过] 文件不存在: {base_file.name} 或 {enhanced_file.name}")
            continue

        print(f"[分析] {base_file.name} vs {enhanced_file.name}")
        result = compare_modules(base_file, enhanced_file)

        if 'error' in result:
            print(f"  [错误] {result['error']}")
            continue

        results.append((str(base_file), str(enhanced_file)))

        # 显示分析结果
        base_info = result['base_info']
        enhanced_info = result['enhanced_info']
        similarity = result['similarity']

        print(f"  基础版本: {base_info['total_lines']} 行, {len(base_info['functions'])} 函数, {len(base_info['classes'])} 类")
        print(f"  增强版本: {enhanced_info['total_lines']} 行, {len(enhanced_info['functions'])} 函数, {len(enhanced_info['classes'])} 类")
        print(f"  相似度: {similarity:.2%}")
        print(f"  共同函数: {len(result['common_functions'])} 个")
        print(f"  基础独有: {len(result['unique_to_base'])} 个")
        print(f"  增强独有: {len(result['unique_to_enhanced'])} 个")
        print(f"  [建议] {result['recommendation']}")
        print()

    # 生成合并计划
    if results:
        plan = generate_merge_plan(results)

        plan_file = project_root / "MERGE_PLAN.md"
        with open(plan_file, 'w', encoding='utf-8') as f:
            f.write(plan)

        print("=" * 70)
        print(f"[完成] 分析完成！合并计划已保存到: {plan_file}")
        print("=" * 70)

        # 显示合并建议总结
        print("\n[总结] 合并建议:")
        for base_file, enhanced_file in results:
            base_name = Path(base_file).stem
            enhanced_name = Path(enhanced_file).stem
            print(f"  - {base_name} → {enhanced_name} (合并)")

    else:
        print("[警告] 未找到重复模块对")


if __name__ == "__main__":
    main()
