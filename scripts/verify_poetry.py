#!/usr/bin/env python3
"""
Poetry安装验证脚本
验证项目是否可以使用Poetry正确安装所有依赖
"""

import os
import sys
import subprocess
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PoetryVerifier:
    """Poetry安装验证器"""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.pyproject_file = self.project_root / "pyproject.toml"

    def check_poetry_installed(self) -> bool:
        """检查Poetry是否已安装"""
        try:
            result = subprocess.run(
                ["poetry", "--version"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info(f"Poetry已安装: {result.stdout.strip()}")
                return True
            else:
                logger.error("Poetry命令执行失败")
                return False
        except FileNotFoundError:
            logger.error("未找到Poetry命令，请先安装Poetry")
            return False

    def verify_pyproject_toml(self) -> bool:
        """验证pyproject.toml文件是否存在并有效"""
        if not self.pyproject_file.exists():
            logger.error(f"pyproject.toml文件不存在: {self.pyproject_file}")
            return False

        logger.info(f"找到pyproject.toml文件: {self.pyproject_file}")

        # 检查文件是否包含必要的配置
        try:
            with open(self.pyproject_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 检查关键配置项
            required_sections = [
                "[tool.poetry]",
                "[tool.poetry.dependencies]",
                "python"
            ]

            missing_sections = []
            for section in required_sections:
                if section not in content:
                    missing_sections.append(section)

            if missing_sections:
                logger.error(f"pyproject.toml缺少必要配置: {', '.join(missing_sections)}")
                return False

            logger.info("pyproject.toml配置有效")
            return True
        except Exception as e:
            logger.error(f"读取pyproject.toml失败: {e}")
            return False

    def verify_lock_file(self) -> bool:
        """验证poetry.lock文件是否存在"""
        lock_file = self.project_root / "poetry.lock"
        if not lock_file.exists():
            logger.warning("poetry.lock文件不存在，将使用'poetry lock'命令创建")
            try:
                result = subprocess.run(
                    ["poetry", "lock", "--no-update"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    logger.info("成功创建poetry.lock文件")
                    return True
                else:
                    logger.error(f"创建poetry.lock失败: {result.stderr}")
                    return False
            except Exception as e:
                logger.error(f"执行poetry lock命令失败: {e}")
                return False
        else:
            logger.info(f"找到poetry.lock文件: {lock_file}")
            return True

    def verify_install(self) -> bool:
        """验证依赖安装"""
        logger.info("开始验证依赖安装...")
        try:
            result = subprocess.run(
                ["poetry", "install"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info("依赖安装成功")
                return True
            else:
                logger.error(f"依赖安装失败: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"执行poetry install命令失败: {e}")
            return False

    def verify_dependencies(self) -> bool:
        """验证关键依赖是否可导入"""
        key_dependencies = [
            "aiohttp",
            "pydantic",
            "pyperclip",
            "openai",
            "tenacity",
            "watchdog"
        ]

        failed_imports = []

        for dep in key_dependencies:
            try:
                result = subprocess.run(
                    ["poetry", "run", "python", "-c", f"import {dep}"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    failed_imports.append(dep)
                    logger.warning(f"无法导入依赖: {dep}")
                else:
                    logger.info(f"成功导入依赖: {dep}")
            except Exception as e:
                failed_imports.append(dep)
                logger.error(f"验证依赖{dep}时出错: {e}")

        if failed_imports:
            logger.error(f"以下依赖无法正确导入: {', '.join(failed_imports)}")
            return False

        logger.info("所有关键依赖验证成功")
        return True

    def verify_dev_dependencies(self) -> bool:
        """验证开发依赖是否可导入"""
        dev_dependencies = [
            "pytest",
            "black",
            "flake8",
            "mypy"
        ]

        failed_imports = []

        for dep in dev_dependencies:
            try:
                result = subprocess.run(
                    ["poetry", "run", "python", "-c", f"import {dep}"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    failed_imports.append(dep)
                    logger.warning(f"无法导入开发依赖: {dep}")
                else:
                    logger.info(f"成功导入开发依赖: {dep}")
            except Exception as e:
                failed_imports.append(dep)
                logger.error(f"验证开发依赖{dep}时出错: {e}")

        if failed_imports:
            logger.warning(f"以下开发依赖无法正确导入: {', '.join(failed_imports)}")
            logger.info("这可能是正常情况，具体取决于项目的dev-dependencies配置")

        return True

    def run_full_verification(self) -> bool:
        """运行完整的验证流程"""
        logger.info("开始Poetry安装验证...")

        steps = [
            ("检查Poetry安装", self.check_poetry_installed),
            ("验证pyproject.toml", self.verify_pyproject_toml),
            ("验证poetry.lock", self.verify_lock_file),
            ("验证依赖安装", self.verify_install),
            ("验证关键依赖", self.verify_dependencies),
            ("验证开发依赖", self.verify_dev_dependencies)
        ]

        all_passed = True
        for step_name, step_func in steps:
            logger.info(f"正在执行: {step_name}")
            if not step_func():
                all_passed = False
                logger.error(f"步骤失败: {step_name}")

        if all_passed:
            logger.info("✅ 所有验证步骤通过！项目已成功配置为使用Poetry")
            return True
        else:
            logger.error("❌ 部分验证步骤失败，请检查上面的错误信息")
            return False


def main():
    """主函数"""
    verifier = PoetryVerifier()
    success = verifier.run_full_verification()

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
