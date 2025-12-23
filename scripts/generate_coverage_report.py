#!/usr/bin/env python3
"""
覆盖率报告生成器
生成详细的覆盖率报告，包括HTML、Markdown和JSON格式
"""

import os
import sys
import json
import argparse
import subprocess
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


class CoverageReportGenerator:
    """覆盖率报告生成器"""
    
    def __init__(self, project_root: Path = None, output_dir: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.output_dir = output_dir or self.project_root / "coverage_reports"
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 确保输出目录存在
        self.output_dir.mkdir(exist_ok=True)
    
    def run_coverage_tests(self, test_path: str = "tests") -> bool:
        """运行覆盖率测试"""
        try:
            print(f"运行覆盖率测试: {test_path}")
            result = subprocess.run(
                ["poetry", "run", "pytest", test_path,
                 "--cov=qbittorrent_monitor",
                 "--cov-report=xml",
                 "--cov-report=html",
                 "--cov-report=json",
                 "--cov-report=term-missing"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"测试运行失败: {result.stderr}")
                return False
            
            print("测试运行成功")
            return True
        except Exception as e:
            print(f"运行覆盖率测试时出错: {e}")
            return False
    
    def parse_coverage_data(self, coverage_json_path: Path) -> Dict[str, Any]:
        """解析覆盖率数据"""
        try:
            with open(coverage_json_path, 'r', encoding='utf-8') as f:
                coverage_data = json.load(f)
            return coverage_data
        except Exception as e:
            print(f"解析覆盖率数据时出错: {e}")
            return {}
    
    def generate_markdown_report(self, coverage_data: Dict[str, Any]) -> Path:
        """生成Markdown格式的覆盖率报告"""
        report_path = self.output_dir / f"coverage_report_{self.timestamp}.md"
        
        # 提取总覆盖率
        total_coverage = coverage_data.get('totals', {}).get('percent_covered', 0)
        
        # 提取文件覆盖率数据
        files_data = coverage_data.get('files', {})
        
        # 生成Markdown内容
        markdown_content = []
        markdown_content.append(f"# 测试覆盖率报告")
        markdown_content.append(f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        markdown_content.append("")
        
        # 总体统计
        markdown_content.append("## 总体统计")
        markdown_content.append(f"- 总覆盖率: {total_coverage:.2f}%")
        markdown_content.append(f"- 覆盖行数: {coverage_data.get('totals', {}).get('covered_lines', 0)}")
        markdown_content.append(f"- 总行数: {coverage_data.get('totals', {}).get('num_statements', 0)}")
        markdown_content.append(f"- 跳过行数: {coverage_data.get('totals', {}).get('missing_lines', 0)}")
        markdown_content.append("")
        
        # 按模块分类
        modules = {}
        for file_path, file_data in files_data.items():
            # 获取模块名
            parts = file_path.split('/')
            if len(parts) > 1:
                module = parts[1]  # 假设第一个部分是模块名
            else:
                module = 'other'
            
            if module not in modules:
                modules[module] = []
            modules[module].append({
                'path': file_path,
                'coverage': file_data.get('summary', {}).get('percent_covered', 0),
                'covered_lines': file_data.get('summary', {}).get('covered_lines', 0),
                'missing_lines': file_data.get('summary', {}).get('missing_lines', 0),
                'num_statements': file_data.get('summary', {}).get('num_statements', 0)
            })
        
        # 按模块显示覆盖率
        markdown_content.append("## 模块覆盖率")
        for module, files in modules.items():
            # 计算模块平均覆盖率
            module_coverage = sum(f['coverage'] for f in files) / len(files)
            markdown_content.append(f"### {module} ({module_coverage:.2f}%)")
            
            # 按覆盖率排序
            sorted_files = sorted(files, key=lambda x: x['coverage'])
            
            # 生成表格
            markdown_content.append("| 文件 | 覆盖率 | 已覆盖 | 总行数 | 未覆盖 |")
            markdown_content.append("|------|--------|--------|--------|--------|")
            
            for file_info in sorted_files:
                file_name = os.path.basename(file_info['path'])
                markdown_content.append(
                    f"| {file_name} | {file_info['coverage']:.2f}% | "
                    f"{file_info['covered_lines']} | {file_info['num_statements']} | "
                    f"{file_info['missing_lines']} |"
                )
            
            markdown_content.append("")
        
        # 改进建议
        markdown_content.append("## 改进建议")
        
        # 找出覆盖率最低的文件
        all_files = []
        for files in modules.values():
            all_files.extend(files)
        
        if all_files:
            # 按覆盖率排序
            sorted_files = sorted(all_files, key=lambda x: x['coverage'])
            
            markdown_content.append("### 优先改进的文件")
            for i, file_info in enumerate(sorted_files[:5]):  # 只显示前5个
                file_name = os.path.basename(file_info['path'])
                markdown_content.append(f"{i+1}. **{file_name}** (覆盖率: {file_info['coverage']:.2f}%)")
            
            markdown_content.append("")
            
            # 统计覆盖率分布
            high_coverage = sum(1 for f in all_files if f['coverage'] >= 90)
            medium_coverage = sum(1 for f in all_files if 70 <= f['coverage'] < 90)
            low_coverage = sum(1 for f in all_files if f['coverage'] < 70)
            
            markdown_content.append("### 覆盖率分布")
            markdown_content.append(f"- 高覆盖率 (≥90%): {high_coverage} 个文件")
            markdown_content.append(f"- 中等覆盖率 (70-90%): {medium_coverage} 个文件")
            markdown_content.append(f"- 低覆盖率 (<70%): {low_coverage} 个文件")
            
            markdown_content.append("")
            
            # 生成建议
            markdown_content.append("### 具体建议")
            
            if low_coverage > 0:
                markdown_content.append("1. **优先为低覆盖率模块添加测试**")
                markdown_content.append("   重点关注覆盖率低于70%的文件，这些文件通常包含关键业务逻辑")
            
            if medium_coverage > 0:
                markdown_content.append("2. **提升中等覆盖率模块的测试质量**")
                markdown_content.append("   为覆盖率在70-90%的模块添加边界条件和异常处理的测试")
            
            markdown_content.append("3. **添加集成测试**")
            markdown_content.append("   确保模块间的交互有适当的测试覆盖")
            
            markdown_content.append("4. **定期运行覆盖率检查**")
            markdown_content.append("   使用 `./scripts/check_coverage.sh` 定期检查覆盖率")
        
        # 添加使用说明
        markdown_content.append("## 使用说明")
        markdown_content.append("### 如何提高覆盖率")
        markdown_content.append("1. 运行覆盖率检查:")
        markdown_content.append("   ```bash")
        markdown_content.append("   ./scripts/check_coverage.sh")
        markdown_content.append("   ```")
        markdown_content.append("")
        markdown_content.append("2. 查看HTML详细报告:")
        markdown_content.append("   ```bash")
        markdown_content.append("   open htmlcov/index.html")
        markdown_content.append("   ```")
        markdown_content.append("")
        markdown_content.append("3. 运行特定模块的测试:")
        markdown_content.append("   ```bash")
        markdown_content.append("   poetry run pytest tests/unit/test_ai_classifier.py -v")
        markdown_content.append("   ```")
        markdown_content.append("")
        markdown_content.append("### 覆盖率目标")
        markdown_content.append("- 总体覆盖率: ≥85%")
        markdown_content.append("- AI分类器: ≥90%")
        markdown_content.append("- qBittorrent客户端: ≥90%")
        markdown_content.append("- 网页爬虫: ≥85%")
        markdown_content.append("- 核心工具函数: ≥90%")
        
        # 写入文件
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(markdown_content))
        
        return report_path
    
    def generate_json_report(self, coverage_data: Dict[str, Any]) -> Path:
        """生成JSON格式的覆盖率报告"""
        report_path = self.output_dir / f"coverage_report_{self.timestamp}.json"
        
        # 添加元数据
        report_data = {
            'generated_at': datetime.datetime.now().isoformat(),
            'project_root': str(self.project_root),
            'coverage_data': coverage_data
        }
        
        # 写入文件
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        return report_path
    
    def generate_html_report(self) -> Optional[Path]:
        """生成HTML格式的覆盖率报告（复制现有的HTML报告）"""
        source_html = self.project_root / "htmlcov" / "index.html"
        if source_html.exists():
            target_html = self.output_dir / f"coverage_report_{self.timestamp}.html"
            
            try:
                # 复制HTML文件
                import shutil
                shutil.copy2(source_html, target_html)
                return target_html
            except Exception as e:
                print(f"复制HTML报告时出错: {e}")
                return None
        else:
            print("HTML覆盖率报告不存在")
            return None
    
    def generate_coverage_badge(self, coverage_data: Dict[str, Any]) -> Optional[Path]:
        """生成覆盖率徽章"""
        total_coverage = coverage_data.get('totals', {}).get('percent_covered', 0)
        
        # 根据覆盖率选择颜色
        if total_coverage >= 90:
            color = "brightgreen"
        elif total_coverage >= 80:
            color = "green"
        elif total_coverage >= 70:
            color = "yellow"
        elif total_coverage >= 60:
            color = "orange"
        else:
            color = "red"
        
        # 生成徽章URL
        badge_url = f"https://img.shields.io/badge/coverage-{total_coverage:.0f}%25-{color}"
        
        # 下载徽章
        badge_path = self.output_dir / f"coverage_badge_{self.timestamp}.svg"
        
        try:
            import requests
            response = requests.get(badge_url)
            if response.status_code == 200:
                with open(badge_path, 'wb') as f:
                    f.write(response.content)
                return badge_path
        except Exception as e:
            print(f"生成覆盖率徽章时出错: {e}")
        
        return None
    
    def generate_all_reports(self, test_path: str = "tests") -> Dict[str, Path]:
        """生成所有格式的覆盖率报告"""
        results = {}
        
        # 运行测试并生成覆盖率数据
        if not self.run_coverage_tests(test_path):
            return results
        
        # 解析覆盖率数据
        coverage_json_path = self.project_root / "coverage.json"
        if not coverage_json_path.exists():
            print("覆盖率JSON文件不存在")
            return results
        
        coverage_data = self.parse_coverage_data(coverage_json_path)
        if not coverage_data:
            print("无法解析覆盖率数据")
            return results
        
        # 生成Markdown报告
        markdown_path = self.generate_markdown_report(coverage_data)
        if markdown_path:
            results['markdown'] = markdown_path
            print(f"Markdown报告已生成: {markdown_path}")
        
        # 生成JSON报告
        json_path = self.generate_json_report(coverage_data)
        if json_path:
            results['json'] = json_path
            print(f"JSON报告已生成: {json_path}")
        
        # 生成HTML报告
        html_path = self.generate_html_report()
        if html_path:
            results['html'] = html_path
            print(f"HTML报告已生成: {html_path}")
        
        # 生成覆盖率徽章
        badge_path = self.generate_coverage_badge(coverage_data)
        if badge_path:
            results['badge'] = badge_path
            print(f"覆盖率徽章已生成: {badge_path}")
        
        return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="生成覆盖率报告")
    parser.add_argument("--test-path", type=str, default="tests", help="测试路径")
    parser.add_argument("--output-dir", type=str, help="输出目录")
    parser.add_argument("--format", type=str, choices=["all", "markdown", "json", "html", "badge"], 
                       default="all", help="报告格式")
    parser.add_argument("--project-root", type=str, help="项目根目录")
    
    args = parser.parse_args()
    
    # 设置路径
    project_root = Path(args.project_root) if args.project_root else None
    output_dir = Path(args.output_dir) if args.output_dir else None
    
    # 创建报告生成器
    generator = CoverageReportGenerator(project_root, output_dir)
    
    # 生成报告
    results = generator.generate_all_reports(args.test_path)
    
    if not results:
        print("报告生成失败")
        sys.exit(1)
    
    # 输出结果
    print("\n覆盖率报告生成完成:")
    for format_type, path in results.items():
        print(f"- {format_type.capitalize()}: {path}")
    
    # 如果只生成了一种格式，直接返回该路径
    if args.format != "all" and args.format in results:
        print(f"\n报告路径: {results[args.format]}")


if __name__ == "__main__":
    main()
