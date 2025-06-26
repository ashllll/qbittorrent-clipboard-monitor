"""
增强的配置管理模块

支持：
- 多种配置格式（JSON, YAML, TOML）
- 环境变量覆盖
- 配置热加载
- 配置验证
"""

import asyncio
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ValidationError
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class CategoryConfig(BaseModel):
    """分类配置数据模型"""

    save_path: str = Field(alias="savePath")
    keywords: List[str] = []
    description: str = ""
    foreign_keywords: Optional[List[str]] = Field(
        default=None, alias="foreign_keywords"
    )
    # 增强规则配置
    rules: Optional[List[Dict[str, Any]]] = None
    priority: int = 0  # 分类优先级

    class Config:
        validate_by_name = True


class PathMappingRule(BaseModel):
    """路径映射规则"""

    source_prefix: str
    target_prefix: str
    description: Optional[str] = None


class QBittorrentConfig(BaseModel):
    """qBittorrent配置数据模型"""

    host: str = "192.168.1.40"
    port: int = 8989
    username: str = "admin"
    password: str = "password"
    use_https: bool = False
    verify_ssl: bool = True
    # 移到这里的路径配置
    use_nas_paths_directly: bool = False
    path_mapping: List[PathMappingRule] = []


class DeepSeekConfig(BaseModel):
    """DeepSeek AI配置数据模型"""

    api_key: str = ""
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    # Few-shot示例
    few_shot_examples: Optional[List[Dict[str, str]]] = None
    prompt_template: str = """你是一个专业的种子分类助手。请根据以下规则，将种子名称分类到最合适的类别中。

种子名称: {torrent_name}

可用分类及其描述:
{category_descriptions}

关键词提示:
{category_keywords}

{few_shot_examples}

分类要求：
1. 仔细分析种子名称中的关键词和特征，特别注意文件扩展名和分辨率信息。
2. 电视剧通常包含S01E01这样的季和集信息，或者包含"剧集"、"Season"、"Episode"等词。
3. 电影通常包含年份(如2020)、分辨率(1080p、4K)或"BluRay"、"WEB-DL"等标签。
4. 成人内容通常包含明显的成人关键词，或成人内容制作商名称。
5. 日本动画通常包含"动画"、"Anime"或"Fansub"等术语。
6. 如果同时符合多个分类，选择最合适的那个。
7. 如果无法确定分类或不属于任何明确分类，返回'other'。

请只返回最合适的分类名称（例如：tv, movies, adult, anime, music, games, software, other），不要包含任何其他解释或文字。"""


class ConsoleNotificationConfig(BaseModel):
    """控制台通知配置"""

    enabled: bool = True
    colored: bool = True
    show_details: bool = True
    show_statistics: bool = True


class NotificationConfig(BaseModel):
    """通知配置"""

    enabled: bool = False
    console: ConsoleNotificationConfig = ConsoleNotificationConfig()
    services: List[str] = []  # telegram, discord, email等
    webhook_url: Optional[str] = None
    api_token: Optional[str] = None
    chat_id: Optional[str] = None
    email_config: Optional[Dict[str, Any]] = None


class AppConfig(BaseModel):
    """应用配置数据模型"""

    qbittorrent: QBittorrentConfig
    deepseek: DeepSeekConfig
    categories: Dict[str, CategoryConfig]
    # 全局路径映射（向后兼容）
    path_mapping: Dict[str, str] = {}
    use_nas_paths_directly: bool = False
    # 监控配置
    check_interval: float = 2.0
    max_retries: int = 3
    retry_delay: float = 5.0
    # 通知配置
    notifications: NotificationConfig = NotificationConfig()
    # 热加载配置
    hot_reload: bool = True
    # 日志配置
    log_level: str = "INFO"
    log_file: Optional[str] = "magnet_monitor.log"


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件变化监控处理器"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger("Config.FileHandler")

    def on_modified(self, event):
        if event.is_directory:
            return

        if event.src_path == str(self.config_manager.config_path):
            self.logger.info(f"配置文件已修改: {event.src_path}")
            # 使用线程安全的方式触发重载
            threading.Thread(target=self._trigger_reload, daemon=True).start()

    def _trigger_reload(self):
        """在新线程中触发配置重载"""
        try:
            # 尝试获取运行中的事件循环
            loop = asyncio.get_running_loop()
            # 线程安全地调度协程
            asyncio.run_coroutine_threadsafe(self.config_manager.reload_config(), loop)
        except RuntimeError:
            # 如果没有运行中的事件循环，创建新的
            try:
                asyncio.run(self.config_manager.reload_config())
            except Exception as e:
                self.logger.error(f"配置重载失败: {str(e)}")


class ConfigManager:
    """增强的配置管理器"""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        self.logger = logging.getLogger("ConfigManager")

        if config_path is None:
            # 使用脚本同目录下的配置文件
            self.config_path = Path(__file__).parent / "config.json"
        else:
            self.config_path = Path(config_path)

        self.config: Optional[AppConfig] = None
        self.observer: Optional[Observer] = None
        self._reload_callbacks: List[callable] = []

    async def load_config(self) -> AppConfig:
        """加载并验证配置文件"""
        if not self.config_path.exists():
            self._create_default_config()

        try:
            config_data = self._load_config_file()
            config_data = self._apply_env_overrides(config_data)
            self.config = AppConfig(**config_data)

            # 启动热加载监控
            if self.config.hot_reload:
                self._start_file_watcher()

            self.logger.info(f"配置加载成功: {self.config_path}")
            return self.config

        except Exception as e:
            from .exceptions import ConfigError

            raise ConfigError(f"配置加载失败: {str(e)}") from e

    def _load_config_file(self) -> Dict[str, Any]:
        """根据文件扩展名加载不同格式的配置文件"""
        suffix = self.config_path.suffix.lower()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                if suffix == ".json":
                    return json.load(f)
                elif suffix in [".yaml", ".yml"]:
                    import yaml

                    return yaml.safe_load(f)
                elif suffix == ".toml":
                    import tomllib

                    return tomllib.load(f)
                else:
                    # 默认尝试JSON
                    return json.load(f)
        except Exception as e:
            raise ValueError(f"配置文件格式错误: {str(e)}") from e

    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """应用环境变量覆盖"""
        # qBittorrent配置覆盖
        qbt_config = config_data.get("qbittorrent", {})
        qbt_config.update(
            {
                "host": os.getenv("QBIT_HOST", qbt_config.get("host", "localhost")),
                "port": int(os.getenv("QBIT_PORT", qbt_config.get("port", 8080))),
                "username": os.getenv("QBIT_USER", qbt_config.get("username", "admin")),
                "password": os.getenv(
                    "QBIT_PASS", qbt_config.get("password", "password")
                ),
            }
        )
        config_data["qbittorrent"] = qbt_config

        # DeepSeek配置覆盖
        deepseek_config = config_data.get("deepseek", {})
        deepseek_config.update(
            {
                "api_key": os.getenv(
                    "DEEPSEEK_API_KEY", deepseek_config.get("api_key", "")
                ),
                "base_url": os.getenv(
                    "DEEPSEEK_BASE_URL",
                    deepseek_config.get("base_url", "https://api.deepseek.com"),
                ),
            }
        )
        config_data["deepseek"] = deepseek_config

        return config_data

    def _start_file_watcher(self):
        """启动配置文件监控"""
        if self.observer is not None:
            return

        self.observer = Observer()
        event_handler = ConfigFileHandler(self)
        self.observer.schedule(
            event_handler, str(self.config_path.parent), recursive=False
        )
        self.observer.start()
        self.logger.info("配置文件热加载监控已启动")

    async def reload_config(self):
        """重新加载配置"""
        try:
            old_config = self.config
            new_config = await self.load_config()

            # 通知所有注册的回调函数
            for callback in self._reload_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(old_config, new_config)
                    else:
                        callback(old_config, new_config)
                except Exception as e:
                    self.logger.error(f"配置重载回调执行失败: {str(e)}")

            self.logger.info("配置重载完成")

        except Exception as e:
            self.logger.error(f"配置重载失败: {str(e)}")

    def register_reload_callback(self, callback: callable):
        """注册配置重载回调函数"""
        self._reload_callbacks.append(callback)

    def stop_file_watcher(self):
        """停止配置文件监控"""
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            self.logger.info("配置文件监控已停止")

    def _create_default_config(self):
        """创建默认配置文件"""
        default_config = {
            "qbittorrent": {
                "host": "localhost",
                "port": 8080,
                "username": "admin",
                "password": "password",
                "use_https": False,
                "verify_ssl": True,
                "use_nas_paths_directly": False,
                "path_mapping": [
                    {
                        "source_prefix": "/downloads",
                        "target_prefix": "/vol1/downloads",
                        "description": "Docker容器到NAS的路径映射",
                    }
                ],
            },
            "deepseek": {
                "api_key": "",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
                "timeout": 30,
                "max_retries": 3,
                "retry_delay": 1.0,
                "few_shot_examples": [
                    {
                        "torrent_name": "Game.of.Thrones.S08E06.1080p.WEB.H264-MEMENTO",
                        "category": "tv",
                    },
                    {
                        "torrent_name": "Avengers.Endgame.2019.1080p.BluRay.x264-SPARKS",
                        "category": "movies",
                    },
                ],
            },
            "categories": {
                "tv": {
                    "savePath": "/downloads/tv/",
                    "keywords": ["S01", "S02", "剧集", "电视剧", "Series", "Episode"],
                    "description": "电视剧、连续剧、剧集等",
                    "priority": 10,
                    "rules": [
                        {"type": "regex", "pattern": r"S\d+E\d+", "score": 5},
                        {
                            "type": "keyword",
                            "keywords": ["Season", "Episode"],
                            "score": 3,
                        },
                    ],
                },
                "movies": {
                    "savePath": "/downloads/movies/",
                    "keywords": [
                        "电影",
                        "Movie",
                        "1080p",
                        "4K",
                        "BluRay",
                        "Remux",
                        "WEB-DL",
                    ],
                    "description": "电影作品",
                    "priority": 8,
                    "rules": [
                        {"type": "regex", "pattern": r"\.(19|20)\d{2}\.", "score": 4},
                        {
                            "type": "keyword",
                            "keywords": ["1080p", "4K", "BluRay"],
                            "score": 3,
                        },
                    ],
                },
                "adult": {
                    "savePath": "/downloads/adult/",
                    "keywords": ["成人", "18+", "xxx", "Porn", "Sex", "Nude", "JAV"],
                    "description": "成人内容",
                    "priority": 15,
                    "foreign_keywords": [
                        "Brazzers",
                        "Naughty America",
                        "Reality Kings",
                    ],
                },
                "anime": {
                    "savePath": "/downloads/anime/",
                    "keywords": ["动画", "动漫", "Anime", "Fansub"],
                    "description": "日本动画、动漫",
                    "priority": 12,
                },
                "music": {
                    "savePath": "/downloads/music/",
                    "keywords": ["音乐", "专辑", "Music", "Album", "FLAC", "MP3"],
                    "description": "音乐专辑、单曲",
                    "priority": 6,
                },
                "games": {
                    "savePath": "/downloads/games/",
                    "keywords": ["游戏", "Game", "ISO", "PC", "PS5", "Switch"],
                    "description": "电子游戏",
                    "priority": 7,
                },
                "software": {
                    "savePath": "/downloads/software/",
                    "keywords": ["软件", "Software", "App", "Crack", "Keygen"],
                    "description": "应用程序、软件",
                    "priority": 5,
                },
                "other": {
                    "savePath": "/downloads/other/",
                    "keywords": [],
                    "description": "其他内容",
                    "priority": 1,
                },
            },
            "check_interval": 2,
            "max_retries": 3,
            "retry_delay": 5,
            "notifications": {
                "enabled": False,
                "console": {
                    "enabled": True,
                    "colored": True,
                    "show_details": True,
                    "show_statistics": True,
                },
                "services": [],
                "webhook_url": None,
            },
            "hot_reload": True,
            "log_level": "INFO",
            "log_file": "magnet_monitor.log",
        }

        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            self.logger.info(f"已创建默认配置文件: {self.config_path}")
        except Exception as e:
            from .exceptions import ConfigError

            raise ConfigError(f"创建默认配置失败: {str(e)}") from e
