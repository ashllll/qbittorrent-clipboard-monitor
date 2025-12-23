"""
智能启动管理器

采用行业标准方案：
- 使用 importlib.metadata 检查依赖 (Python 3.8+)
- 使用 pip check 验证完整性
- 使用延迟加载优化启动速度
"""

import sys
import subprocess
import os
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class StartupConfig:
    """启动配置"""
    project_root: Optional[Path] = None
    marker_file_name: str = ".installation_marker"
    core_packages: List[str] = field(default_factory=lambda: [
        "aiohttp", "pydantic", "openai",
        "tenacity", "watchdog", "beautifulsoup4",
        "pyperclip", "colorama", "psutil"
    ])
    quiet_mode: bool = False


@dataclass
class StartupStatus:
    """启动状态"""
    is_ready: bool = False
    is_first_run: bool = True
    environment_ok: bool = False
    dependencies_ok: bool = False
    missing_packages: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class DependencyChecker:
    """
    依赖检查器
    
    使用行业标准工具：
    - importlib.metadata (Python 3.8+)
    - pip check
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
    
    def check_package_installed(self, package_name: str) -> bool:
        """检查包是否已安装 (使用 importlib.metadata)"""
        try:
            from importlib.metadata import version
            version(package_name)
            return True
        except Exception:
            return False
    
    def get_package_version(self, package_name: str) -> Optional[str]:
        """获取已安装版本"""
        try:
            from importlib.metadata import version
            return version(package_name)
        except Exception:
            return None
    
    def verify_dependencies_with_pip(self) -> Tuple[bool, List[str]]:
        """使用 pip check 验证依赖完整性"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "check"],
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )
            
            if result.returncode == 0:
                return True, []
            
            # 解析缺失的依赖
            missing = []
            for line in result.stdout.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if 'not installed' in line.lower():
                    # 格式: "package not installed"
                    parts = line.split()
                    if parts:
                        pkg = parts[0]
                        missing.append(pkg)
                elif 'has unmet dependency' in line.lower():
                    # 格式: "package has unmet dependency: dep"
                    parts = line.split(':')
                    if parts:
                        pkg = parts[0].strip()
                        missing.append(pkg)
            
            return False, missing
            
        except subprocess.SubprocessError as e:
            logger.error(f"pip check 执行失败: {e}")
            return False, []
    
    def get_all_installed_packages(self) -> Dict[str, str]:
        """获取所有已安装包及版本"""
        packages = {}
        try:
            from importlib.metadata import distributions
            for dist in distributions():
                for name in dist.metadata.get_all('Name', []):
                    packages[name.lower()] = dist.version
        except Exception as e:
            logger.warning(f"获取已安装包列表失败: {e}")
        return packages
    
    def verify_core_dependencies(self, core_packages: List[str]) -> Tuple[bool, List[str]]:
        """验证核心依赖"""
        missing = []
        for pkg in core_packages:
            if not self.check_package_installed(pkg):
                missing.append(pkg)
        return len(missing) == 0, missing


class StartupManager:
    """
    智能启动管理器
    
    采用行业标准方案实现"一次配置，永久可用"
    """
    
    def __init__(self, config: Optional[StartupConfig] = None):
        self.config = config or StartupConfig()
        self.project_root = self.config.project_root or Path(__file__).parent.parent
        self.marker_file = self.project_root / self.config.marker_file_name
        self.checker = DependencyChecker(self.project_root)
        
        # 预热缓存的模块
        self._prewarm_modules = False
    
    def is_first_run(self) -> bool:
        """检查是否是首次运行"""
        return not self.marker_file.exists()
    
    def mark_initialized(self):
        """标记已初始化"""
        try:
            self.marker_file.touch()
            logger.info(f"已创建安装标记文件: {self.marker_file}")
        except Exception as e:
            logger.error(f"创建安装标记失败: {e}")
    
    def check_environment(self) -> Tuple[bool, Optional[str]]:
        """检查运行环境"""
        # 检查 Python 版本
        version_info = sys.version_info
        if version_info < (3, 9):
            return False, f"Python 版本过低: {version_info.major}.{version_info.minor}, 需要 >= 3.9"
        
        # 检查是否在虚拟环境中
        in_venv = hasattr(sys, 'real_prefix') or (
            hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
        )
        
        if not in_venv:
            logger.warning("未检测到虚拟环境，建议在虚拟环境中运行")
        
        return True, None
    
    def verify_dependencies(self) -> Tuple[bool, List[str]]:
        """验证依赖完整性"""
        # 首先验证核心依赖
        core_ok, core_missing = self.checker.verify_core_dependencies(
            self.config.core_packages
        )
        
        if not core_ok:
            return False, core_missing
        
        # 使用 pip check 全面验证
        pip_ok, pip_missing = self.checker.verify_dependencies_with_pip()
        
        if not pip_ok:
            # 合并缺失列表
            all_missing = list(set(core_missing + pip_missing))
            return False, all_missing
        
        return True, []
    
    def repair_dependencies(self, packages: Optional[List[str]] = None) -> bool:
        """修复依赖"""
        try:
            if packages:
                # 只安装指定的包
                cmd = [sys.executable, "-m", "pip", "install"] + packages
            else:
                # 重新安装所有依赖
                cmd = [sys.executable, "-m", "pip", "install", "-e", str(self.project_root)]
            
            if self.config.quiet_mode:
                cmd.append("-q")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.project_root)
            )
            
            if result.returncode == 0:
                logger.info("依赖修复成功")
                return True
            else:
                logger.error(f"依赖修复失败: {result.stderr}")
                return False
                
        except subprocess.SubprocessError as e:
            logger.error(f"依赖修复执行失败: {e}")
            return False
    
    def run_initial_setup(self, quiet: bool = False) -> bool:
        """运行首次设置"""
        logger.info("首次运行，执行环境初始化...")
        
        # 检查环境
        env_ok, env_msg = self.check_environment()
        if not env_ok:
            logger.error(f"环境检查失败: {env_msg}")
            return False
        
        # 验证依赖
        deps_ok, missing = self.verify_dependencies()
        
        if not deps_ok:
            logger.warning(f"发现缺失依赖: {missing}")
            
            if not quiet:
                logger.info("自动安装缺失依赖...")
            
            if not self.repair_dependencies(missing):
                logger.error("依赖安装失败")
                return False
        
        # 标记初始化完成
        self.mark_initialized()
        
        logger.info("初始化完成")
        return True
    
    def check_and_prepare(self, auto_repair: bool = True) -> StartupStatus:
        """检查并准备启动环境"""
        status = StartupStatus()
        status.timestamp = datetime.now()
        
        # 检查是否是首次运行
        status.is_first_run = self.is_first_run()
        
        if status.is_first_run:
            logger.info("首次运行，开始初始化...")
            status.is_ready = self.run_initial_setup(quiet=not auto_repair)
            return status
        
        # 检查环境
        env_ok, env_msg = self.check_environment()
        status.environment_ok = env_ok
        if not env_ok:
            status.error_message = env_msg
            status.is_ready = False
            return status
        
        # 验证依赖
        deps_ok, missing = self.verify_dependencies()
        status.dependencies_ok = deps_ok
        status.missing_packages = missing
        
        if deps_ok:
            status.is_ready = True
        else:
            status.is_ready = False
            status.error_message = f"缺失依赖: {', '.join(missing)}"
            
            if auto_repair:
                logger.warning(f"自动修复缺失依赖: {missing}")
                if self.repair_dependencies(missing):
                    status.is_ready = True
                    status.dependencies_ok = True
                    status.missing_packages = []
                    # 更新标记时间
                    self.mark_initialized()
        
        return status
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前安装状态"""
        installed = self.checker.get_all_installed_packages()
        
        return {
            "is_first_run": self.is_first_run(),
            "marker_exists": self.marker_file.exists(),
            "marker_path": str(self.marker_file),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "installed_packages_count": len(installed),
            "core_packages": {
                pkg: self.checker.get_package_version(pkg)
                for pkg in self.config.core_packages
            },
            "dependencies_ok": self.verify_dependencies()[0],
        }


# 全局启动管理器实例
_startup_manager: Optional[StartupManager] = None


def get_startup_manager() -> StartupManager:
    """获取全局启动管理器"""
    global _startup_manager
    if _startup_manager is None:
        _startup_manager = StartupManager()
    return _startup_manager


def check_and_prepare(auto_repair: bool = True) -> StartupStatus:
    """便捷函数：检查并准备启动环境"""
    manager = get_startup_manager()
    return manager.check_and_prepare(auto_repair=auto_repair)


def is_initialized() -> bool:
    """检查是否已初始化"""
    manager = get_startup_manager()
    return not manager.is_first_run()


def ensure_initialized(quiet: bool = False) -> bool:
    """确保环境已初始化"""
    manager = get_startup_manager()
    if manager.is_first_run():
        return manager.run_initial_setup(quiet=quiet)
    return True
