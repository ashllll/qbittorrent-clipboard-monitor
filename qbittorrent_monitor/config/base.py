"""基础配置模块

提供 Config 根数据类和序列化逻辑。
"""

from __future__ import annotations

import json
import logging
import os
import stat
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Any, Optional

from ..exceptions import ConfigError
from .constants import VALID_LOG_LEVELS, MIN_CHECK_INTERVAL, MAX_CHECK_INTERVAL
from .qb import QBConfig
from .ai import AIConfig
from .categories import CategoryConfig, get_default_categories
from .database import DatabaseConfig
from .metrics import MetricsConfig
from .plugins import PluginConfig
from .validators import parse_bool, parse_int, parse_float, validate_non_empty_string
from ..security import validate_hostname, validate_url

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """应用配置根对象
    
    包含所有模块的配置信息，支持从字典和文件加载。
    
    Attributes:
        qbittorrent: qBittorrent 连接配置
        ai: AI 分类器配置
        categories: 分类规则字典，键为分类名称
        check_interval: 剪贴板检查间隔（秒）
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        database: 数据库配置
        metrics: Prometheus 指标导出配置
        plugins: 插件系统配置
    
    Example:
        >>> config = Config()
        >>> config.validate()  # 验证配置
        >>> config.save("/path/to/config.json")  # 保存配置
    """
    qbittorrent: QBConfig = field(default_factory=QBConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    categories: Dict[str, CategoryConfig] = field(default_factory=dict)
    check_interval: float = 1.0
    log_level: str = "INFO"
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    plugins: PluginConfig = field(default_factory=PluginConfig)

    def __post_init__(self):
        """初始化后设置默认值"""
        if not self.categories:
            self.categories = get_default_categories()

    def validate(self, strict: bool = False) -> List[str]:
        """验证所有配置项
        
        Args:
            strict: 如果为 True，验证失败时抛出异常；
                   如果为 False，返回警告列表
        
        Returns:
            警告信息列表（仅当 strict=False 时）
        
        Raises:
            ConfigError: 当 strict=True 且配置无效时抛出
        """
        warnings: List[str] = []
        
        # 验证 qBittorrent 配置
        try:
            self.qbittorrent.validate()
        except ConfigError as e:
            if strict:
                raise
            warnings.append(f"qBittorrent 配置警告: {e}")

        # 验证 AI 配置
        try:
            self.ai.validate()
        except ConfigError as e:
            if strict:
                raise
            warnings.append(f"AI 配置警告: {e}")

        # 验证分类配置
        for name, cat in self.categories.items():
            try:
                cat.validate(name)
            except ConfigError as e:
                if strict:
                    raise
                warnings.append(str(e))

        # 验证日志级别
        if self.log_level.upper() not in VALID_LOG_LEVELS:
            msg = f"LOG_LEVEL 必须是以下值之一: {', '.join(VALID_LOG_LEVELS)}，当前值: {self.log_level}"
            if strict:
                raise ConfigError(msg)
            warnings.append(msg)
        else:
            self.log_level = self.log_level.upper()

        # 验证检查间隔
        if not isinstance(self.check_interval, (int, float)):
            msg = f"CHECK_INTERVAL 必须是数字，当前值: {self.check_interval}"
            if strict:
                raise ConfigError(msg)
            warnings.append(msg)
        elif not (MIN_CHECK_INTERVAL <= self.check_interval <= MAX_CHECK_INTERVAL):
            msg = (
                f"CHECK_INTERVAL 必须在 {MIN_CHECK_INTERVAL}-{MAX_CHECK_INTERVAL} 范围内，"
                f"当前值: {self.check_interval}"
            )
            if strict:
                raise ConfigError(msg)
            warnings.append(msg)
        
        # 验证数据库配置
        try:
            self.database.validate()
        except ConfigError as e:
            if strict:
                raise
            warnings.append(f"数据库配置警告: {e}")
        
        # 验证指标配置
        try:
            self.metrics.validate()
        except ConfigError as e:
            if strict:
                raise
            warnings.append(f"指标配置警告: {e}")
        
        # 验证插件配置
        try:
            self.plugins.validate()
        except ConfigError as e:
            if strict:
                raise
            warnings.append(f"插件配置警告: {e}")

        return warnings

    async def verify_qb_connection(self) -> Dict[str, Any]:
        """验证 qBittorrent 连接
        
        Returns:
            连接验证结果字典
        """
        return await self.qbittorrent.verify_connection()

    def to_dict(self) -> dict:
        """将配置转换为字典
        
        Returns:
            配置的字典表示
        """
        return {
            "qbittorrent": asdict(self.qbittorrent),
            "ai": asdict(self.ai),
            "categories": {
                name: asdict(cat) for name, cat in self.categories.items()
            },
            "check_interval": self.check_interval,
            "log_level": self.log_level,
            "database": asdict(self.database),
            "metrics": asdict(self.metrics),
            "plugins": asdict(self.plugins),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """从字典创建配置对象
        
        Args:
            data: 配置字典
            
        Returns:
            Config 实例
            
        Raises:
            ConfigError: 当配置格式无效时抛出
        """
        try:
            return cls(
                qbittorrent=QBConfig(**data.get("qbittorrent", {})),
                ai=AIConfig(**data.get("ai", {})),
                categories={
                    name: CategoryConfig(**cat)
                    for name, cat in data.get("categories", {}).items()
                },
                check_interval=data.get("check_interval", 1.0),
                log_level=data.get("log_level", "INFO"),
                database=DatabaseConfig(**data.get("database", {})),
                metrics=MetricsConfig(**data.get("metrics", {})),
                plugins=PluginConfig(**data.get("plugins", {})),
            )
        except TypeError as e:
            raise ConfigError(f"配置格式错误: {e}")
        except Exception as e:
            raise ConfigError(f"加载配置时发生错误: {e}")

    def save(self, path: Optional[Path] = None) -> None:
        """保存配置到 JSON 文件
        
        Args:
            path: 配置文件路径，默认使用 ~/.config/qb-monitor/config.json
        """
        if path is None:
            path = Path.home() / ".config" / "qb-monitor" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # 设置安全的文件权限（仅用户可读写）
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        # 设置文件权限为 0o600（仅用户可读写）
        try:
            if sys.platform != 'win32':
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
                logger.debug(f"配置文件权限已设置为 0o600: {path}")
            else:
                # Windows 使用 ACL（如果需要）
                import subprocess
                try:
                    subprocess.run(
                        ['icacls', str(path), '/inheritance:r', '/grant:r', 
                         f'{os.getlogin()}:F'],
                        check=True,
                        capture_output=True
                    )
                except (subprocess.CalledProcessError, FileNotFoundError):
                    logger.warning("Windows 上无法设置文件权限，请确保配置文件安全")
        except Exception as e:
            logger.warning(f"无法设置配置文件权限: {e}")
        
        logger.debug(f"配置已保存到: {path}")

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """从 JSON 文件加载配置
        
        Args:
            path: 配置文件路径，默认使用 ~/.config/qb-monitor/config.json
            
        Returns:
            Config 实例
            
        Raises:
            ConfigError: 当配置文件格式无效时抛出
        """
        if path is None:
            path = Path.home() / ".config" / "qb-monitor" / "config.json"
        
        if not path.exists():
            logger.info(f"配置文件不存在，创建默认配置: {path}")
            config = cls()
            config.save(path)
            return config
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ConfigError(f"配置文件 JSON 格式错误 ({path}): {e}")
        except Exception as e:
            raise ConfigError(f"加载配置文件失败 ({path}): {e}")
