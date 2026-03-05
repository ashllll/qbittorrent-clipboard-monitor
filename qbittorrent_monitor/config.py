"""简化版配置管理模块"""

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


def load_config(path: Optional[Path] = None) -> Config:
    """加载配置的便捷函数"""
    return Config.load(path)
