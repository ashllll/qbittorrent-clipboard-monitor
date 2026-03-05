"""简化版配置管理模块

支持从 JSON 配置文件和环境变量加载配置。
环境变量优先级高于配置文件。
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class QBConfig:
    """qBittorrent配置"""
    host: str = "localhost"
    port: int = 8080
    username: str = "admin"
    password: str = "adminadmin"
    use_https: bool = False


@dataclass
class AIConfig:
    """AI分类器配置"""
    enabled: bool = True
    api_key: str = ""
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com/v1"
    timeout: int = 30
    max_retries: int = 3


@dataclass
class CategoryConfig:
    """分类配置"""
    save_path: str
    keywords: List[str] = field(default_factory=list)


@dataclass
class Config:
    """应用配置"""
    qbittorrent: QBConfig = field(default_factory=QBConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    categories: Dict[str, CategoryConfig] = field(default_factory=dict)
    check_interval: float = 1.0
    log_level: str = "INFO"
    
    def __post_init__(self):
        if not self.categories:
            self.categories = self._default_categories()
    
    def _default_categories(self) -> Dict[str, CategoryConfig]:
        """默认分类配置"""
        return {
            "movies": CategoryConfig(
                save_path="/downloads/movies",
                keywords=["电影", "Movie", "1080p", "4K", "BluRay", "WEB-DL"]
            ),
            "tv": CategoryConfig(
                save_path="/downloads/tv",
                keywords=["S01", "E01", "电视剧", "Series", "Season"]
            ),
            "anime": CategoryConfig(
                save_path="/downloads/anime",
                keywords=["动画", "Anime", "[GM-Team]"]
            ),
            "music": CategoryConfig(
                save_path="/downloads/music",
                keywords=["音乐", "Music", "FLAC", "MP3", "Album"]
            ),
            "software": CategoryConfig(
                save_path="/downloads/software",
                keywords=["软件", "Software", "Portable", "Crack"]
            ),
            "other": CategoryConfig(
                save_path="/downloads/other",
                keywords=[]
            ),
        }
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "qbittorrent": asdict(self.qbittorrent),
            "ai": asdict(self.ai),
            "categories": {
                name: asdict(cat) for name, cat in self.categories.items()
            },
            "check_interval": self.check_interval,
            "log_level": self.log_level,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """从字典创建配置"""
        return cls(
            qbittorrent=QBConfig(**data.get("qbittorrent", {})),
            ai=AIConfig(**data.get("ai", {})),
            categories={
                name: CategoryConfig(**cat) 
                for name, cat in data.get("categories", {}).items()
            },
            check_interval=data.get("check_interval", 1.0),
            log_level=data.get("log_level", "INFO"),
        )
    
    def save(self, path: Optional[Path] = None) -> None:
        """保存配置到文件"""
        if path is None:
            path = Path.home() / ".config" / "qb-monitor" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """从文件加载配置"""
        if path is None:
            path = Path.home() / ".config" / "qb-monitor" / "config.json"
        if not path.exists():
            config = cls()
            config.save(path)
            return config
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


def _load_from_env(config: Config) -> None:
    """从环境变量加载配置，覆盖现有配置"""
    # qBittorrent 配置
    if host := os.getenv("QBIT_HOST"):
        config.qbittorrent.host = host
    if port := os.getenv("QBIT_PORT"):
        config.qbittorrent.port = int(port)
    if username := os.getenv("QBIT_USERNAME"):
        config.qbittorrent.username = username
    if password := os.getenv("QBIT_PASSWORD"):
        config.qbittorrent.password = password
    if use_https := os.getenv("QBIT_USE_HTTPS"):
        config.qbittorrent.use_https = use_https.lower() in ("true", "1", "yes")
    
    # AI 配置
    if ai_enabled := os.getenv("AI_ENABLED"):
        config.ai.enabled = ai_enabled.lower() in ("true", "1", "yes")
    if api_key := os.getenv("AI_API_KEY"):
        config.ai.api_key = api_key
    if model := os.getenv("AI_MODEL"):
        config.ai.model = model
    if base_url := os.getenv("AI_BASE_URL"):
        config.ai.base_url = base_url
    
    # 应用配置
    if interval := os.getenv("CHECK_INTERVAL"):
        config.check_interval = float(interval)
    if log_level := os.getenv("LOG_LEVEL"):
        config.log_level = log_level.upper()


def load_config(path: Optional[Path] = None) -> Config:
    """加载配置的便捷函数
    
    加载顺序：
    1. 从配置文件加载（如果不存在则创建默认配置）
    2. 从环境变量加载并覆盖
    
    Args:
        path: 配置文件路径，默认使用 ~/.config/qb-monitor/config.json
        
    Returns:
        配置对象
    """
    # 从配置文件加载
    config = Config.load(path)
    
    # 从环境变量加载并覆盖
    _load_from_env(config)
    
    return config
