"""配置管理器模块

支持热重载和配置变更回调。
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import List, Callable, Optional

from ..exceptions import ConfigError
from .base import Config
from .env_loader import load_from_env

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器 - 支持热重载
    
    管理配置文件的加载、验证和热重载功能。
    
    Attributes:
        config_path: 配置文件路径
        auto_reload: 是否启用自动重载
        reload_interval: 自动重载检查间隔（秒）

    Example:
        >>> manager = ConfigManager(auto_reload=True)
        >>> config = manager.get_config()
        >>> # 配置文件修改后
        >>> config = manager.get_config()  # 自动获取最新配置
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        auto_reload: bool = False,
        reload_interval: float = 5.0
    ):
        """初始化配置管理器
        
        Args:
            config_path: 配置文件路径
            auto_reload: 是否启用自动重载
            reload_interval: 自动重载检查间隔（秒）
        """
        self.config_path = config_path or (Path.home() / ".config" / "qb-monitor" / "config.json")
        self._config: Optional[Config] = None
        self._last_modified: float = 0
        self._last_check: float = 0
        self.auto_reload = auto_reload
        self.reload_interval = reload_interval
        self._callbacks: List[Callable[[Config], None]] = []

    def get_config(self, force_reload: bool = False) -> Config:
        """获取当前配置
        
        如果启用了自动重载，会检查文件是否修改并自动重新加载。
        
        Args:
            force_reload: 强制重新加载配置
            
        Returns:
            当前配置对象
        """
        current_time = time.time()
        
        # 检查是否需要重新加载
        need_reload = (
            self._config is None or
            force_reload or
            (self.auto_reload and current_time - self._last_check > self.reload_interval)
        )
        
        if need_reload and self.config_path.exists():
            self._last_check = current_time
            current_modified = self.config_path.stat().st_mtime
            
            if force_reload or self._config is None or current_modified > self._last_modified:
                logger.info("检测到配置文件变更，正在重新加载...")
                old_config = self._config
                self._config = self._load_config()
                self._last_modified = current_modified
                
                # 执行回调
                if old_config is not None:  # 不是首次加载
                    for callback in self._callbacks:
                        try:
                            callback(self._config)
                        except Exception as e:
                            logger.error(f"配置变更回调执行失败: {e}")
        
        if self._config is None:
            self._config = self._load_config()
        
        return self._config

    def _load_config(self) -> Config:
        """加载配置（内部方法）
        
        Returns:
            加载的配置对象
        """
        config = Config.load(self.config_path)
        config.validate(strict=True)
        load_from_env(config)  # 环境变量覆盖
        config.validate(strict=True)  # 再次验证
        return config

    def reload(self) -> Config:
        """强制重新加载配置
        
        Returns:
            最新的配置对象
        """
        return self.get_config(force_reload=True)

    def on_change(self, callback: Callable[[Config], None]) -> None:
        """注册配置变更回调函数
        
        Args:
            callback: 配置变更时调用的函数，接收新的配置对象
        """
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[Config], None]) -> bool:
        """移除配置变更回调函数
        
        Args:
            callback: 要移除的回调函数
            
        Returns:
            是否成功移除
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            return True
        return False
