"""默认值常量定义

定义系统中各种配置的默认值。
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class Defaults:
    """系统默认配置"""
    
    # qBittorrent 连接
    QBIT_HOST: str = "localhost"
    QBIT_PORT: int = 8080
    QBIT_USERNAME: str = "admin"
    QBIT_USE_HTTPS: bool = False
    
    # AI 配置
    AI_ENABLED: bool = False
    AI_MODEL: str = "MiniMax-M2.5"
    AI_BASE_URL: str = "https://api.minimaxi.com/v1"
    AI_TIMEOUT: int = 30
    AI_MAX_RETRIES: int = 3
    
    # 监控配置
    CHECK_INTERVAL: float = 1.0
    DEBOUNCE_SECONDS: float = 2.0
    
    # 轮询配置
    ACTIVE_INTERVAL: float = 0.5
    IDLE_INTERVAL: float = 3.0
    IDLE_THRESHOLD: float = 30.0
    BURST_WINDOW: float = 5.0
    BURST_THRESHOLD: int = 3
    
    # 日志
    LOG_LEVEL: str = "INFO"
    MAX_LOG_LENGTH: int = 100
    
    # 指标服务器
    METRICS_ENABLED: bool = True
    METRICS_HOST: str = "0.0.0.0"
    METRICS_PORT: int = 9090
    METRICS_PATH: str = "/metrics"
    
    # 数据库
    DATABASE_ENABLED: bool = True
    DATABASE_AUTO_CLEANUP_DAYS: int = 0
    DATABASE_EXPORT_FORMAT: str = "json"
    
    # 插件
    PLUGINS_ENABLED: bool = True
    PLUGINS_AUTO_ENABLE: bool = False
    PLUGINS_AUTO_DISCOVER: bool = True
    
    # 重试配置
    RETRY_BASE_DELAY: float = 1.0
    RETRY_MAX_DELAY: float = 10.0
    RETRY_EXPONENTIAL_BASE: float = 2.0
    RETRY_MAX_ATTEMPTS: int = 3


@dataclass(frozen=True)
class Categories:
    """默认分类配置"""
    
    MOVIES: Dict[str, List[str]] = field(default_factory=lambda: {
        "save_path": "/downloads/movies",
        "keywords": [
            # 质量标识
            "1080p", "720p", "480p", "4K", "UHD", "HDR", 
            "BluRay", "Blu-ray", "BDrip", "BRrip",
            "WEB-DL", "WEBRip", "WEB", "HDTV", "HDCAM", 
            "CAM", "TS", "TC", "DVDrip", "DVDRip",
            # 编码格式
            "x264", "x265", "HEVC", "AVC", "H.264", "H.265", "10bit", "8bit",
            # 音频
            "DTS", "TrueHD", "Atmos", "DD5.1", "AAC", "AC3",
            # 类型
            "电影", "Movie", "Film", "Complete", "Director's Cut", 
            "Extended", "Unrated", "Remastered", "Criterion", "IMAX",
        ]
    })
    
    TV: Dict[str, List[str]] = field(default_factory=lambda: {
        "save_path": "/downloads/tv",
        "keywords": [
            # 季集标识
            "S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10",
            "S11", "S12", "S13", "S14", "S15", "S20", "S25", "S30",
            "E01", "E02", "E03", "E04", "E05", "E06", "E07", "E08", "E09", "E10",
            "E11", "E12", "E13", "E14", "E15", "E20", "E22", "E24",
            "Season", "Episode", "Complete Season", "Season Complete",
            # 类型
            "电视剧", "Series", "TV Series", "TV Show", "Show",
            # 质量
            "1080p", "720p", "4K", "WEB-DL", "BluRay", "HDTV",
        ]
    })
    
    ANIME: Dict[str, List[str]] = field(default_factory=lambda: {
        "save_path": "/downloads/anime",
        "keywords": [
            # 类型
            "动画", "Anime", "Animation",
            # 字幕组
            "[GM-Team]", "[喵萌奶茶屋]", "[诸神字幕组]", "[桜都字幕组]",
            "[极影字幕社]", "[澄空学园]", "[华盟字幕社]", "[轻之国度]",
            "[动漫国字幕组]", "[漫猫字幕组]", "[DHR字幕组]",
            # 标识
            "BD", "TV版", "剧场版", "OVA", "OAD", "SP", "特典",
            "Season", "第", "季", "话", "集",
        ]
    })
    
    MUSIC: Dict[str, List[str]] = field(default_factory=lambda: {
        "save_path": "/downloads/music",
        "keywords": [
            # 音频格式
            "FLAC", "MP3", "MP4", "AAC", "ALAC", "WAV", "DSD", "SACD",
            "320kbps", "256kbps", "192kbps", "128kbps", "V0", "V2",
            # 类型
            "音乐", "Music", "Album", "EP", "Single", "Compilation",
            "OST", "Soundtrack", "Live", "Concert", "Remix", "Cover",
            # 发行
            "Discography", "Greatest Hits", "Best Of", "Anthology",
            "Deluxe Edition", "Limited Edition", "Bonus Tracks",
        ]
    })
    
    SOFTWARE: Dict[str, List[str]] = field(default_factory=lambda: {
        "save_path": "/downloads/software",
        "keywords": [
            # 类型
            "软件", "Software", "Program", "Application", "App",
            # 版本
            "v1.", "v2.", "v3.", "v4.", "v5.", "v6.", "v7.", "v8.", "v9.", "v10.",
            "Portable", "Repack", "Preactivated", "Activated",
            "Crack", "Keygen", "Patch", "License", "Serial",
            # 系统
            "Windows", "Linux", "macOS", "Mac", "Android", "iOS",
            # 开发
            "IDE", "Editor", "Tool", "Utility", "Driver", "Update",
        ]
    })
    
    GAMES: Dict[str, List[str]] = field(default_factory=lambda: {
        "save_path": "/downloads/games",
        "keywords": [
            # 平台
            "PC", "Steam", "GOG", "Epic",
            # 类型
            "Game", "Games", "Gaming",
            # 发布组
            "CODEX", "PLAZA", "HOODLUM", "FLT", "DARKSiDERS", "TiNYiSO",
            "SKIDROW", "RELOADED", "CPY", "FitGirl", "DODI",
            "Razor1911", "PROPHET", "HI2U", "ALiAS",
            # 版本
            "REPACK", "GOTY", "Deluxe", "Ultimate", "Complete",
            "Update", "DLC", "Expansion",
        ]
    })
    
    BOOKS: Dict[str, List[str]] = field(default_factory=lambda: {
        "save_path": "/downloads/books",
        "keywords": [
            # 格式
            "PDF", "EPUB", "MOBI", "AZW3", "AZW", "DJVU", "CBR", "CBZ",
            # 类型
            "Book", "Ebook", "电子书", "书籍", "小说", "Novel",
            # 出版
            "Publisher", "Edition", "Vol.", "Volume", "Chapter",
        ]
    })
    
    OTHER: Dict[str, List[str]] = field(default_factory=lambda: {
        "save_path": "/downloads/other",
        "keywords": []
    })
    
    @classmethod
    def get_all(cls) -> Dict[str, Dict[str, List[str]]]:
        """获取所有默认分类"""
        return {
            "movies": cls.MOVIES,
            "tv": cls.TV,
            "anime": cls.ANIME,
            "music": cls.MUSIC,
            "software": cls.SOFTWARE,
            "games": cls.GAMES,
            "books": cls.BOOKS,
            "other": cls.OTHER,
        }
