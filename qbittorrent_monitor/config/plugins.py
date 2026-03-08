"""插件系统配置模块

提供 PluginConfig 数据类和验证逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..exceptions import ConfigError


@dataclass
class PluginConfig:
    """插件系统配置
    
    Attributes:
        enabled: 是否启用插件系统
        plugins_dir: 外部插件目录路径，None 使用默认值
        auto_enable: 是否自动启用所有已加载的插件
        auto_discover: 是否自动发现插件
        enabled_plugins: 明确启用的插件列表，空列表表示启用所有
        disabled_plugins: 明确禁用的插件列表
        plugin_configs: 各插件的具体配置，键为插件名
    
    Example:
        >>> config = PluginConfig(
        ...     enabled=True,
        ...     auto_enable=False,
        ...     enabled_plugins=["webhook_notifier", "dingtalk_notifier"],
        ...     plugin_configs={
        ...         "webhook_notifier": {
        ...             "url": "https://hooks.example.com/notify"
        ...         }
        ...     }
        ... )
    """
    enabled: bool = True
    plugins_dir: Optional[str] = None
    auto_enable: bool = False
    auto_discover: bool = True
    enabled_plugins: List[str] = field(default_factory=list)
    disabled_plugins: List[str] = field(default_factory=list)
    plugin_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def validate(self) -> None:
        """验证插件配置
        
        Raises:
            ConfigError: 当配置无效时抛出
        """
        if not isinstance(self.enabled, bool):
            raise ConfigError(f"PLUGINS_ENABLED 必须是布尔值，当前值: {self.enabled}")
        
        if not isinstance(self.auto_enable, bool):
            raise ConfigError(f"PLUGINS_AUTO_ENABLE 必须是布尔值，当前值: {self.auto_enable}")
        
        if not isinstance(self.auto_discover, bool):
            raise ConfigError(f"PLUGINS_AUTO_DISCOVER 必须是布尔值，当前值: {self.auto_discover}")
        
        if self.plugins_dir and not isinstance(self.plugins_dir, str):
            raise ConfigError(f"PLUGINS_DIR 必须是字符串，当前值: {self.plugins_dir}")
        
        # 检查插件目录是否存在（如果配置）
        if self.plugins_dir:
            path = Path(self.plugins_dir)
            if path.exists() and not path.is_dir():
                raise ConfigError(f"PLUGINS_DIR 必须是目录: {self.plugins_dir}")
