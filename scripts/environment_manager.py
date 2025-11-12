#!/usr/bin/env python3
"""
智能环境管理器
自动检测和配置Python虚拟环境、依赖安装、环境变量
"""

import os
import sys
import venv
import subprocess
import platform
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SmartEnvironmentManager:
    """智能环境管理器 - 自动配置虚拟环境和依赖"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.venv_path = self.project_root / "venv"
        self.python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        self.platform = platform.system().lower()

        # 环境配置文件
        self.env_file = self.project_root / ".env"
        self.env_example_file = self.project_root / ".env.example"
        self.requirements_files = [
            self.project_root / "requirements.txt",
            self.project_root / "requirements-dev.txt"
        ]
        self.pyproject_file = self.project_root / "pyproject.toml"

        logger.info(f"环境管理器初始化完成 - Python {self.python_version} on {self.platform}")

    def check_python_compatibility(self) -> Tuple[bool, str]:
        """检查Python版本兼容性"""
        min_version = (3, 9)
        max_version = (3, 12)

        current_version = sys.version_info[:2]

        if current_version < min_version:
            return False, f"Python版本过低 {current_version[0]}.{current_version[1]}, 需要 >= {min_version[0]}.{min_version[1]}"
        elif current_version > max_version:
            return False, f"Python版本过高 {current_version[0]}.{current_version[1]}, 建议 <= {max_version[0]}.{max_version[1]}"

        return True, f"Python版本兼容 {current_version[0]}.{current_version[1]}"

    def create_virtual_env(self, force: bool = False) -> bool:
        """创建虚拟环境"""
        if self.venv_path.exists() and not force:
            logger.info(f"虚拟环境已存在: {self.venv_path}")
            return True

        try:
            logger.info(f"创建虚拟环境: {self.venv_path}")
            venv.create(self.venv_path, with_pip=True, system_site_packages=False)

            # 升级pip到最新版本
            self._run_venv_command("pip install --upgrade pip setuptools wheel")

            logger.info("✅ 虚拟环境创建成功")
            return True

        except Exception as e:
            logger.error(f"❌ 创建虚拟环境失败: {e}")
            return False

    def get_venv_python(self) -> Path:
        """获取虚拟环境中的Python可执行文件"""
        if self.platform == "windows":
            return self.venv_path / "Scripts" / "python.exe"
        else:
            return self.venv_path / "bin" / "python"

    def get_venv_pip(self) -> Path:
        """获取虚拟环境中的pip可执行文件"""
        if self.platform == "windows":
            return self.venv_path / "Scripts" / "pip.exe"
        else:
            return self.venv_path / "bin" / "pip"

    def _run_venv_command(self, command: str, capture_output: bool = True) -> subprocess.CompletedProcess:
        """在虚拟环境中运行命令"""
        venv_python = self.get_venv_python()

        full_command = f"{venv_python} -m {command}"

        logger.debug(f"执行命令: {full_command}")

        try:
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=capture_output,
                text=True,
                cwd=self.project_root
            )
            return result
        except Exception as e:
            logger.error(f"命令执行失败: {full_command}, 错误: {e}")
            raise

    def install_dependencies(self) -> bool:
        """安装项目依赖"""
        success = True

        # 检查pyproject.toml是否存在（Poetry项目）
        if self.pyproject_file.exists():
            logger.info("检测到Poetry项目，尝试安装Poetry...")
            if self._install_poetry():
                success &= self._install_with_poetry()
            else:
                logger.warning("Poetry安装失败，回退到pip安装")
                success &= self._install_with_pip()
        else:
            # 传统pip安装
            success &= self._install_with_pip()

        return success

    def _install_poetry(self) -> bool:
        """安装Poetry"""
        try:
            # 检查poetry是否已安装
            result = subprocess.run(
                ["poetry", "--version"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.info("Poetry已安装")
                return True
        except FileNotFoundError:
            pass

        try:
            logger.info("安装Poetry...")
            subprocess.run([
                sys.executable, "-m", "pip", "install", "poetry"
            ], check=True, capture_output=True)

            # 安装poetry到系统（如果需要）
            logger.info("配置Poetry...")
            subprocess.run([
                sys.executable, "-m", "poetry", "config", "virtualenvs.create", "true"
            ], check=True, capture_output=True)

            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Poetry安装失败: {e}")
            return False

    def _install_with_poetry(self) -> bool:
        """使用Poetry安装依赖"""
        try:
            logger.info("使用Poetry安装依赖...")

            # 创建poetry.lock
            subprocess.run([
                "poetry", "lock", "--no-update"
            ], check=True, cwd=self.project_root)

            # 安装依赖
            subprocess.run([
                "poetry", "install"
            ], check=True, cwd=self.project_root)

            logger.info("✅ Poetry依赖安装完成")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Poetry依赖安装失败: {e}")
            return False

    def _install_with_pip(self) -> bool:
        """使用pip安装依赖"""
        success = True

        for req_file in self.requirements_files:
            if req_file.exists():
                try:
                    logger.info(f"安装依赖文件: {req_file}")

                    # 使用虚拟环境的pip
                    venv_pip = self.get_venv_pip()

                    subprocess.run([
                        str(venv_pip), "install", "-r", str(req_file)
                    ], check=True, cwd=self.project_root)

                    logger.info(f"✅ {req_file.name} 安装完成")

                except subprocess.CalledProcessError as e:
                    logger.error(f"❌ {req_file.name} 安装失败: {e}")
                    success = False

        return success

    def setup_environment_variables(self) -> bool:
        """设置环境变量"""
        try:
            # 创建.env.example文件
            self._create_env_example()

            # 如果.env不存在，从.example复制
            if not self.env_file.exists() and self.env_example_file.exists():
                shutil.copy2(self.env_example_file, self.env_file)
                logger.info(f"已创建环境变量文件: {self.env_file}")

            # 加载并验证环境变量
            env_config = self._load_env_file()
            if self._validate_environment(env_config):
                logger.info("✅ 环境变量配置完成")
                return True
            else:
                logger.warning("⚠️ 环境变量配置需要手动调整")
                return False

        except Exception as e:
            logger.error(f"环境变量配置失败: {e}")
            return False

    def _create_env_example(self):
        """创建环境变量示例文件"""
        env_example = """# qBittorrent 配置
QBT_HOST=localhost
QBT_PORT=8080
QBT_USERNAME=admin
QBT_PASSWORD=adminadmin

# AI 分类器配置
AI_PROVIDER=deepseek
AI_API_KEY=your_deepseek_api_key_here
AI_MODEL=deepseek-chat

# 监控配置
MONITOR_CHECK_INTERVAL=1.0
MONITOR_ADAPTIVE_INTERVAL=true
MONITOR_MIN_INTERVAL=0.1
MONITOR_MAX_INTERVAL=5.0

# 缓存配置
CACHE_ENABLE_DUPLICATE_FILTER=true
CACHE_SIZE=1000
CACHE_TTL_SECONDS=300

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/qbittorrent-monitor.log

# 网页爬虫配置
CRAWLER_ENABLED=false
CRAWLER_MAX_CONCURRENT=5
CRAWLER_DELAY=1.0

# 性能优化
PERFORMANCE_FAST_START=true
PERFORMANCE_MEMORY_POOL=true
PERFORMANCE_BATCH_SIZE=10

# Web界面 (可选)
WEB_ENABLED=false
WEB_HOST=0.0.0.0
WEB_PORT=8081

# 通知配置 (可选)
NOTIFICATIONS_ENABLED=false
NOTIFICATION_EMAIL_SMTP_HOST=
NOTIFICATION_EMAIL_SMTP_PORT=587
NOTIFICATION_EMAIL_USERNAME=
NOTIFICATION_EMAIL_PASSWORD=
NOTIFICATION_EMAIL_TO=
"""

        with open(self.env_example_file, 'w', encoding='utf-8') as f:
            f.write(env_example)

        logger.info(f"已创建环境变量示例: {self.env_example_file}")

    def _load_env_file(self) -> Dict[str, str]:
        """加载环境变量文件"""
        env_config = {}

        if self.env_file.exists():
            with open(self.env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_config[key.strip()] = value.strip()

        return env_config

    def _validate_environment(self, env_config: Dict[str, str]) -> bool:
        """验证环境配置"""
        required_vars = ['QBT_HOST', 'QBT_PORT', 'QBT_USERNAME', 'QBT_PASSWORD']
        missing_vars = []

        for var in required_vars:
            if var not in env_config or not env_config[var]:
                missing_vars.append(var)

        if missing_vars:
            logger.warning(f"缺少必要的环境变量: {', '.join(missing_vars)}")
            return False

        # 验证端口号
        try:
            port = int(env_config.get('QBT_PORT', 8080))
            if not (1 <= port <= 65535):
                raise ValueError(f"端口号无效: {port}")
        except ValueError:
            logger.error("QBT_PORT必须是1-65535之间的数字")
            return False

        return True

    def create_startup_scripts(self) -> bool:
        """创建启动脚本"""
        try:
            # 创建启动脚本
            if self.platform == "windows":
                self._create_windows_startup_script()
            else:
                self._create_unix_startup_script()

            # 创建激活脚本
            self._create_activate_script()

            logger.info("✅ 启动脚本创建完成")
            return True

        except Exception as e:
            logger.error(f"启动脚本创建失败: {e}")
            return False

    def _create_windows_startup_script(self):
        """创建Windows启动脚本"""
        script_content = f"""@echo off
echo 启动 qBittorrent 剪贴板监控器...

REM 激活虚拟环境
call "{self.venv_path}\\Scripts\\activate.bat"

REM 设置Python路径
set PYTHONPATH={self.project_root}

REM 启动程序
python "{self.project_root}\\start.py"

pause
"""

        script_file = self.project_root / "run.bat"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script_content)

        logger.info(f"Windows启动脚本: {script_file}")

    def _create_unix_startup_script(self):
        """创建Unix/Linux/macOS启动脚本"""
        script_content = f"""#!/bin/bash
set -e

echo "启动 qBittorrent 剪贴板监控器..."

# 激活虚拟环境
source "{self.venv_path}/bin/activate"

# 设置Python路径
export PYTHONPATH="{self.project_root}"

# 启动程序
exec python "{self.project_root}/start.py"
"""

        script_file = self.project_root / "run.sh"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script_content)

        # 设置执行权限
        os.chmod(script_file, 0o755)

        logger.info(f"Unix启动脚本: {script_file}")

    def _create_activate_script(self):
        """创建环境激活脚本"""
        if self.platform == "windows":
            script_content = f"""@echo off
echo 激活虚拟环境...
call "{self.venv_path}\\Scripts\\activate.bat"
echo 虚拟环境已激活: {self.venv_path}
echo Python: %VIRTUAL_ENV%\\Scripts\\python.exe
"""
            script_file = self.project_root / "activate_env.bat"
        else:
            script_content = f"""#!/bin/bash
echo "激活虚拟环境..."
source "{self.venv_path}/bin/activate"
echo "虚拟环境已激活: {self.venv_path}"
echo "Python: $(which python)"
"""
            script_file = self.project_root / "activate_env.sh"
            os.chmod(script_file, 0o755)

        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script_content)

        logger.info(f"环境激活脚本: {script_file}")

    def run_system_checks(self) -> Dict[str, bool]:
        """运行系统检查"""
        checks = {}

        # Python版本检查
        checks['python_version'] = self.check_python_compatibility()[0]

        # 虚拟环境检查
        checks['virtual_env'] = self.venv_path.exists() and self.get_venv_python().exists()

        # 依赖检查
        checks['dependencies'] = self._check_dependencies()

        # 配置文件检查
        checks['config_files'] = self._check_config_files()

        # 网络连接检查
        checks['network'] = self._check_network_connectivity()

        return checks

    def _check_dependencies(self) -> bool:
        """检查关键依赖是否安装"""
        try:
            result = self._run_venv_command("import aiohttp, pydantic, openai", capture_output=True)
            return result.returncode == 0
        except:
            return False

    def _check_config_files(self) -> bool:
        """检查配置文件是否存在"""
        required_files = [self.env_file]
        return all(f.exists() for f in required_files)

    def _check_network_connectivity(self) -> bool:
        """检查网络连接"""
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except:
            return False

    def print_environment_info(self):
        """打印环境信息"""
        print("\n" + "="*60)
        print("🚀 qBittorrent 剪贴板监控器 - 环境信息")
        print("="*60)
        print(f"📁 项目路径: {self.project_root}")
        print(f"🐍 Python版本: {self.python_version}")
        print(f"💻 操作系统: {self.platform.title()}")
        print(f"📦 虚拟环境: {self.venv_path}")

        if self.venv_path.exists():
            venv_python = self.get_venv_python()
            print(f"✅ 虚拟环境Python: {venv_python}")

        # 运行系统检查
        checks = self.run_system_checks()
        print("\n📋 系统检查:")
        for check_name, status in checks.items():
            status_icon = "✅" if status else "❌"
            status_text = "通过" if status else "失败"
            print(f"   {status_icon} {check_name}: {status_text}")

        print("="*60)

    def setup_complete_environment(self, force: bool = False) -> bool:
        """完整环境设置"""
        print("🔧 开始完整环境配置...")

        # 1. 检查Python兼容性
        compatible, message = self.check_python_compatibility()
        if not compatible:
            logger.error(f"❌ {message}")
            return False

        logger.info(f"✅ {message}")

        # 2. 创建虚拟环境
        if not self.create_virtual_env(force=force):
            logger.error("❌ 虚拟环境创建失败")
            return False

        # 3. 安装依赖
        if not self.install_dependencies():
            logger.error("❌ 依赖安装失败")
            return False

        # 4. 配置环境变量
        self.setup_environment_variables()

        # 5. 创建启动脚本
        if not self.create_startup_scripts():
            logger.error("❌ 启动脚本创建失败")
            return False

        # 6. 打印环境信息
        self.print_environment_info()

        logger.info("🎉 环境配置完成！可以运行以下命令启动:")
        if self.platform == "windows":
            logger.info("   run.bat")
        else:
            logger.info("   ./run.sh")

        return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="智能环境管理器")
    parser.add_argument("--force", action="store_true", help="强制重新创建虚拟环境")
    parser.add_argument("--check", action="store_true", help="仅运行系统检查")
    parser.add_argument("--info", action="store_true", help="显示环境信息")

    args = parser.parse_args()

    env_manager = SmartEnvironmentManager()

    if args.info:
        env_manager.print_environment_info()
        return

    if args.check:
        checks = env_manager.run_system_checks()
        print("\n📋 系统检查结果:")
        for check_name, status in checks.items():
            status_icon = "✅" if status else "❌"
            status_text = "通过" if status else "失败"
            print(f"   {status_icon} {check_name}: {status_text}")
        return

    # 完整环境设置
    success = env_manager.setup_complete_environment(force=args.force)

    if success:
        print("\n🎉 环境配置成功！")
        print("现在可以启动程序了:")
        if platform.system().lower() == "windows":
            print("   run.bat")
        else:
            print("   ./run.sh")
    else:
        print("\n❌ 环境配置失败，请查看错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()