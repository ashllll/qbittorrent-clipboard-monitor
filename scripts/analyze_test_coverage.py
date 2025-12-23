#!/usr/bin/env python3
"""
测试覆盖率分析脚本
分析项目的测试覆盖率，识别未覆盖的代码区域
"""

import os
import sys
import subprocess
import json
from pathlib import Path
import logging
import argparse
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TestCoverageAnalyzer:
    """测试覆盖率分析器"""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.test_dir = self.project_root / "tests"
        self.source_dir = self.project_root / "qbittorrent_monitor"
        self.coverage_reports_dir = self.project_root / "htmlcov"
        self.coverage_xml = self.project_root / "coverage.xml"

    def run_tests_with_coverage(self) -> bool:
        """运行测试并生成覆盖率报告"""
        try:
            # 运行测试并生成覆盖率报告
            logger.info("运行测试并生成覆盖率报告...")
            result = subprocess.run(
                [
                    "poetry", "run", "pytest",
                    "--cov=qbittorrent_monitor",
                    "--cov-report=xml",
                    "--cov-report=html",
                    "--cov-report=term-missing",
                    "-v"
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                logger.error(f"测试运行失败: {result.stderr}")
                return False

            logger.info("测试运行成功")
            return True
        except Exception as e:
            logger.error(f"运行测试时出错: {e}")
            return False

    def parse_coverage_xml(self) -> Optional[Dict]:
        """解析覆盖率XML报告"""
        try:
            if not self.coverage_xml.exists():
                logger.error(f"覆盖率XML报告不存在: {self.coverage_xml}")
                return None

            tree = ET.parse(self.coverage_xml)
            root = tree.getroot()

            # 提取总体覆盖率信息
            coverage_data = {
                "line_rate": float(root.get("line-rate", "0")),
                "lines_covered": int(root.get("lines-covered", "0")),
                "lines_valid": int(root.get("lines-valid", "0")),
                "branch_rate": float(root.get("branch-rate", "0")),
                "branches_covered": int(root.get("branches-covered", "0")),
                "branches_valid": int(root.get("branches-valid", "0")),
                "packages": []
            }

            # 提取每个包的覆盖率信息
            for package in root.findall(".//package"):
                package_data = {
                    "name": package.get("name", ""),
                    "line_rate": float(package.get("line-rate", "0")),
                    "branch_rate": float(package.get("branch-rate", "0")),
                    "classes": []
                }

                for class_elem in package.findall(".//class"):
                    class_data = {
                        "name": class_elem.get("name", ""),
                        "filename": class_elem.get("filename", ""),
                        "line_rate": float(class_elem.get("line-rate", "0")),
                        "branch_rate": float(class_elem.get("branch-rate", "0")),
                        "lines": []
                    }

                    # 提取未覆盖的行号
                    lines_elem = class_elem.find("lines")
                    if lines_elem is not None:
                        for line in lines_elem.findall("line"):
                            if line.get("hits") == "0":
                                class_data["lines"].append(int(line.get("number", "0")))

                    package_data["classes"].append(class_data)

                coverage_data["packages"].append(package_data)

            return coverage_data
        except Exception as e:
            logger.error(f"解析覆盖率XML时出错: {e}")
            return None

    def find_source_files(self) -> List[Path]:
        """查找所有源代码文件"""
        source_files = []
        for root, dirs, files in os.walk(self.source_dir):
            # 跳过__pycache__目录
            if "__pycache__" in dirs:
                dirs.remove("__pycache__")
            
            for file in files:
                if file.endswith(".py"):
                    source_files.append(Path(root) / file)

        return source_files

    def check_test_files(self) -> Dict[str, bool]:
        """检查每个源代码文件是否有对应的测试文件"""
        test_map = {}
        source_files = self.find_source_files()

        for source_file in source_files:
            # 生成可能的测试文件路径
            relative_path = source_file.relative_to(self.source_dir)
            
            # 转换路径分隔符
            module_parts = list(relative_path.with_suffix("").parts)
            
            # 生成测试文件名
            test_file_name = f"test_{'_'.join(module_parts)}.py"
            
            # 在tests目录中查找可能的测试文件
            possible_test_paths = [
                self.test_dir / "unit" / test_file_name,
                self.test_dir / "integration" / test_file_name,
                self.test_dir / test_file_name
            ]
            
            # 检查测试文件是否存在
            test_exists = any(test_path.exists() for test_path in possible_test_paths)
            
            test_map[str(relative_path)] = test_exists

        return test_map

    def identify_untested_modules(self, coverage_data: Dict) -> List[str]:
        """识别没有测试的模块"""
        untested_modules = []
        
        if not coverage_data or "packages" not in coverage_data:
            return untested_modules

        for package in coverage_data["packages"]:
            if package["line_rate"] == 0:
                for class_data in package["classes"]:
                    if class_data["line_rate"] == 0:
                        untested_modules.append(class_data["filename"])

        return untested_modules

    def identify_partially_tested_modules(self, coverage_data: Dict) -> List[Tuple[str, float, List[int]]]:
        """识别部分测试的模块"""
        partially_tested = []
        
        if not coverage_data or "packages" not in coverage_data:
            return partially_tested

        for package in coverage_data["packages"]:
            # 跳过包本身
            for class_data in package["classes"]:
                # 只关注行覆盖率小于100%但大于0%的文件
                if 0 < class_data["line_rate"] < 1.0:
                    partially_tested.append((
                        class_data["filename"],
                        class_data["line_rate"],
                        class_data["lines"]
                    ))

        return partially_tested

    def generate_coverage_report(self, output_file: Optional[Path] = None) -> bool:
        """生成详细的覆盖率报告"""
        try:
            # 首先运行测试生成覆盖率报告
            if not self.run_tests_with_coverage():
                return False

            # 解析覆盖率XML
            coverage_data = self.parse_coverage_xml()
            if coverage_data is None:
                return False

            # 检查测试文件存在情况
            test_file_map = self.check_test_files()

            # 识别未测试和部分测试的模块
            untested_modules = self.identify_untested_modules(coverage_data)
            partially_tested_modules = self.identify_partially_tested_modules(coverage_data)

            # 生成报告
            report_content = self._generate_report_content(
                coverage_data, test_file_map, untested_modules, partially_tested_modules
            )

            # 输出报告
            if output_file:
                output_file.write_text(report_content, encoding="utf-8")
                logger.info(f"覆盖率报告已保存到: {output_file}")
            else:
                print(report_content)

            return True
        except Exception as e:
            logger.error(f"生成覆盖率报告时出错: {e}")
            return False

    def _generate_report_content(
        self, 
        coverage_data: Dict, 
        test_file_map: Dict[str, bool],
        untested_modules: List[str],
        partially_tested_modules: List[Tuple[str, float, List[int]]]
    ) -> str:
        """生成报告内容"""
        report_lines = []
        
        # 添加标题和总体统计
        report_lines.append("# 测试覆盖率分析报告")
        report_lines.append("")
        report_lines.append(f"## 总体统计")
        report_lines.append(f"- 总覆盖率: {coverage_data['line_rate']:.1%}")
        report_lines.append(f"- 覆盖行数: {coverage_data['lines_covered']} / {coverage_data['lines_valid']}")
        report_lines.append(f"- 分支覆盖率: {coverage_data['branch_rate']:.1%}")
        report_lines.append("")
        
        # 未测试的模块
        report_lines.append("## 未测试的模块")
        if untested_modules:
            report_lines.append("以下模块完全没有测试覆盖:")
            for module in untested_modules:
                report_lines.append(f"- {module}")
        else:
            report_lines.append("✅ 所有模块都有测试覆盖")
        report_lines.append("")
        
        # 部分测试的模块
        report_lines.append("## 部分测试的模块")
        if partially_tested_modules:
            report_lines.append("以下模块有部分测试覆盖:")
            for filename, coverage, missing_lines in partially_tested_modules:
                report_lines.append(f"- **{filename}** - 覆盖率: {coverage:.1%}")
                if missing_lines:
                    report_lines.append(f"  - 未覆盖的行: {', '.join(map(str, missing_lines[:10]))}")
                    if len(missing_lines) > 10:
                        report_lines.append(f"  - ... 还有 {len(missing_lines) - 10} 行")
        else:
            report_lines.append("✅ 所有有测试的模块都达到了100%覆盖率")
        report_lines.append("")
        
        # 测试文件存在情况
        report_lines.append("## 测试文件存在情况")
        report_lines.append("以下源文件缺少对应的测试文件:")
        missing_tests = [module for module, has_test in test_file_map.items() if not has_test]
        if missing_tests:
            for module in missing_tests:
                report_lines.append(f"- {module}")
        else:
            report_lines.append("✅ 所有源文件都有对应的测试文件")
        report_lines.append("")
        
        # 建议
        report_lines.append("## 改进建议")
        if untested_modules or partially_tested_modules:
            report_lines.append("基于分析结果，建议优先为以下模块添加测试:")
            
            # 首先列出完全未测试的模块
            if untested_modules:
                report_lines.append("### 高优先级 - 完全未测试的模块")
                for module in untested_modules:
                    report_lines.append(f"- {module}")
            
            # 然后列出覆盖率低于80%的模块
            low_coverage = [m for m in partially_tested_modules if m[1] < 0.8]
            if low_coverage:
                report_lines.append("### 中等优先级 - 覆盖率低于80%的模块")
                for filename, coverage, _ in low_coverage:
                    report_lines.append(f"- {filename} (当前覆盖率: {coverage:.1%})")
        else:
            report_lines.append("🎉 测试覆盖率已经很高，继续保持!")
        
        return "\n".join(report_lines)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="测试覆盖率分析工具")
    parser.add_argument("--output", type=str, help="输出报告文件路径")
    parser.add_argument("--module", type=str, help="分析特定模块的覆盖率")
    
    args = parser.parse_args()
    
    output_file = None
    if args.output:
        output_file = Path(args.output)
    
    analyzer = TestCoverageAnalyzer()
    success = analyzer.generate_coverage_report(output_file)
    
    if success:
        print("\n✅ 覆盖率分析完成！")
        if output_file:
            print(f"报告已保存到: {output_file}")
        print("查看HTML格式的详细报告:")
        htmlcov_dir = Path("htmlcov")
        if htmlcov_dir.exists():
            print(f"  {htmlcov_dir / 'index.html'}")
    else:
        print("\n❌ 覆盖率分析失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
