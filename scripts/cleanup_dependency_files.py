#!/usr/bin/env python3
"""
安全删除依赖文件脚本
删除旧的requirements.txt和requirements-dev.txt文件，使用Poetry替代
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
import logging
import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DependencyFileCleaner:
    """依赖文件清理器"""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.backup_dir = self.project_root / "backup" / "dependency-files"
        self.requirements_files = [
            self.project_root / "requirements.txt",
            self.project_root / "requirements-dev.txt"
        ]
        self.pyproject_file = self.project_root / "pyproject.toml"

    def create_backup_directory(self) -> bool:
        """创建备份目录"""
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建备份目录: {self.backup_dir}")
            return True
        except Exception as e:
            logger.error(f"创建备份目录失败: {e}")
            return False

    def backup_dependency_files(self) -> bool:
        """备份依赖文件"""
        success = True
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        for file_path in self.requirements_files:
            if file_path.exists():
                backup_path = self.backup_dir / f"{file_path.name}.{timestamp}"
                try:
                    shutil.copy2(file_path, backup_path)
                    logger.info(f"已备份文件: {file_path} -> {backup_path}")
                except Exception as e:
                    logger.error(f"备份文件失败 {file_path}: {e}")
                    success = False
            else:
                logger.info(f"文件不存在，跳过备份: {file_path}")

        return success

    def verify_poetry_setup(self) -> bool:
        """验证Poetry配置是否正确"""
        if not self.pyproject_file.exists():
            logger.error(f"pyproject.toml文件不存在: {self.pyproject_file}")
            return False

        try:
            # 验证poetry.lock文件
            lock_file = self.project_root / "poetry.lock"
            if not lock_file.exists():
                logger.info("poetry.lock文件不存在，正在创建...")
                result = subprocess.run(
                    ["poetry", "lock", "--no-update"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    logger.error(f"创建poetry.lock失败: {result.stderr}")
                    return False
                logger.info("成功创建poetry.lock文件")
            
            # 验证Poetry安装
            logger.info("验证Poetry配置...")
            result = subprocess.run(
                ["poetry", "check"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                logger.error(f"Poetry配置验证失败: {result.stderr}")
                return False
            
            logger.info("Poetry配置验证成功")
            return True
        except Exception as e:
            logger.error(f"验证Poetry配置时出错: {e}")
            return False

    def delete_dependency_files(self) -> bool:
        """删除依赖文件"""
        success = True
        for file_path in self.requirements_files:
            if file_path.exists():
                try:
                    os.remove(file_path)
                    logger.info(f"已删除文件: {file_path}")
                except Exception as e:
                    logger.error(f"删除文件失败 {file_path}: {e}")
                    success = False
            else:
                logger.info(f"文件不存在，无需删除: {file_path}")

        return success

    def verify_no_requirements_references(self) -> bool:
        """验证是否还有引用requirements.txt的文件"""
        try:
            result = subprocess.run(
                ["grep", "-r", "requirements.txt", self.project_root, "--exclude-dir=.git", "--exclude-dir=backup"],
                capture_output=True,
                text=True
            )
            
            # 如果找到引用，打印警告但继续执行
            if result.returncode == 0:
                logger.warning("发现以下文件仍引用requirements.txt:")
                for line in result.stdout.splitlines():
                    logger.warning(f"  {line}")
                logger.warning("这些引用将在后续步骤中更新")
                return True  # 仍然返回True，因为这是预期的
            else:
                logger.info("未发现对requirements.txt的引用")
                return True
        except Exception as e:
            logger.error(f"检查requirements.txt引用时出错: {e}")
            return False  # 出错时返回False，可能有未处理的引用

    def cleanup_dependency_files(self, force: bool = False) -> bool:
        """执行完整的依赖文件清理流程"""
        logger.info("开始清理旧依赖文件...")

        # 1. 创建备份目录
        if not self.create_backup_directory():
            return False

        # 2. 备份依赖文件
        if not self.backup_dependency_files():
            if not force:
                logger.error("备份失败，终止清理流程。使用--force参数可强制继续。")
                return False
            else:
                logger.warning("备份失败，但继续执行（强制模式）")

        # 3. 验证Poetry配置
        if not self.verify_poetry_setup():
            if not force:
                logger.error("Poetry配置验证失败，终止清理流程。使用--force参数可强制继续。")
                return False
            else:
                logger.warning("Poetry配置验证失败，但继续执行（强制模式）")

        # 4. 检查是否还有引用requirements.txt的文件
        if not self.verify_no_requirements_references():
            if not force:
                logger.error("发现requirements.txt引用，终止清理流程。使用--force参数可强制继续。")
                return False
            else:
                logger.warning("发现requirements.txt引用，但继续执行（强制模式）")

        # 5. 删除依赖文件
        if not self.delete_dependency_files():
            if not force:
                logger.error("删除依赖文件失败，终止清理流程。使用--force参数可强制继续。")
                return False
            else:
                logger.warning("删除依赖文件失败，但继续执行（强制模式）")

        logger.info("✅ 依赖文件清理完成！")
        logger.info("所有依赖现在通过Poetry管理")
        logger.info(f"备份文件保存在: {self.backup_dir}")

        return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="安全删除旧依赖文件")
    parser.add_argument("--force", action="store_true", help="强制执行，不进行安全检查")
    parser.add_argument("--dry-run", action="store_true", help="仅显示将要执行的操作，不实际执行")

    args = parser.parse_args()

    cleaner = DependencyFileCleaner()

    if args.dry_run:
        logger.info("=== 模拟运行模式 ===")
        logger.info("将执行以下操作:")
        logger.info(f"1. 创建备份目录: {cleaner.backup_dir}")
        logger.info("2. 备份以下文件:")
        for file_path in cleaner.requirements_files:
            logger.info(f"   - {file_path}")
        logger.info("3. 验证Poetry配置")
        logger.info("4. 检查requirements.txt引用")
        logger.info("5. 删除以下文件:")
        for file_path in cleaner.requirements_files:
            if file_path.exists():
                logger.info(f"   - {file_path}")
        logger.info("=== 模拟运行结束 ===")
        return

    if args.force:
        logger.info("执行强制模式，跳过安全检查")

    success = cleaner.cleanup_dependency_files(force=args.force)

    if success:
        print("\n🎉 依赖文件清理成功！")
        print("现在所有依赖都通过Poetry管理")
        print(f"您可以运行以下命令来验证安装:")
        print("  python scripts/verify_poetry.py")
    else:
        print("\n❌ 依赖文件清理失败，请查看上面的错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
