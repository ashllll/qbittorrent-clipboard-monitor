"""数据库配置模块

提供 DatabaseConfig 数据类和验证逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..exceptions_unified import ConfigurationError


@dataclass
class DatabaseConfig:
    """数据库配置
    
    Attributes:
        enabled: 是否启用数据持久化
        db_path: 数据库文件路径
        auto_cleanup_days: 自动清理旧数据的天数，0 表示不自动清理
        export_format: 默认导出格式 (json/csv)
    
    Example:
        >>> config = DatabaseConfig(
        ...     enabled=True,
        ...     db_path="~/.local/share/qb-monitor/monitor.db",
        ...     auto_cleanup_days=30,
        ...     export_format="json"
        ... )
    """
    enabled: bool = True
    db_path: str = "~/.local/share/qb-monitor/monitor.db"
    auto_cleanup_days: int = 0  # 0 表示不自动清理
    export_format: str = "json"

    def validate(self) -> None:
        """验证数据库配置
        
        Raises:
            ConfigurationError: 当配置项无效时抛出
        """
        if not isinstance(self.enabled, bool):
            raise ConfigurationError(f"DATABASE_ENABLED 必须是布尔值，当前值: {self.enabled}")
        
        if not self.db_path or not isinstance(self.db_path, str):
            raise ConfigurationError(f"DATABASE_PATH 必须是有效的字符串，当前值: {self.db_path}")
        
        if not isinstance(self.auto_cleanup_days, int) or self.auto_cleanup_days < 0:
            raise ConfigurationError(f"DATABASE_AUTO_CLEANUP_DAYS 必须是非负整数，当前值: {self.auto_cleanup_days}")
        
        if self.export_format not in ("json", "csv"):
            raise ConfigurationError(f"DATABASE_EXPORT_FORMAT 必须是 'json' 或 'csv'，当前值: {self.export_format}")
