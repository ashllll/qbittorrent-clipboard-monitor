"""
Web爬虫模块

提供网页内容抓取和磁力链接提取功能

⚠️ 注意：此模块正在进行重构
    - 旧的 WebCrawler 类仍在原位置
    - 新模块正在逐步迁移中
    - 完整迁移预计需要1-2周时间
"""

# 保持向后兼容：从旧位置导入
# TODO: 迁移完成后移除此导入
try:
    from ..web_crawler import WebCrawler as _OldWebCrawler
    WebCrawler = _OldWebCrawler
except ImportError:
    # 如果旧文件不存在，使用新的模块
    # 注意：这些模块可能尚未完全实现
    try:
        from .models import SiteConfig, MemoryMonitor
        from .cache import CacheManager
        from .resilience import ResilienceManager
        from .stats import StatsCollector

        # 创建WebCrawler占位符（实际实现待添加）
        class WebCrawler:
            """WebCrawler - 新架构（重构中）"""
            def __init__(self, config, qbt_client):
                raise NotImplementedError("新架构WebCrawler正在开发中，请使用旧的web_crawler模块")

    except ImportError as e:
        raise ImportError(
            "WebCrawler模块迁移中，旧文件和新文件都不可用。"
            f"错误: {e}"
        )

# 导出已实现的新模块
try:
    from .models import SiteConfig, MemoryMonitor
    from .cache import CacheManager
    from .resilience import ResilienceManager
    from .stats import StatsCollector
    from .adapters import (
        SiteAdapter,
        GenericSiteAdapter,
        TorrentSiteAdapter,
        MagnetLinkAdapter,
        AdapterFactory,
        AdaptiveParser,
        SiteType,
    )
    from .optimizer import (
        OptimizationLevel,
        SmartConcurrencyController,
        OptimizedAsyncWebCrawler,
        PerformanceOptimizer,
    )
    from .core import (
        WebCrawler as NewWebCrawler,
        CrawlRequest,
        CrawlResult,
        CrawlStatus,
        ContentType,
        CrawlerStats,
    )

    __all__ = [
        # 主类
        "WebCrawler",  # 保持向后兼容
        "NewWebCrawler",
        "CrawlRequest",
        "CrawlResult",
        "CrawlStatus",
        "ContentType",
        "CrawlerStats",
        # 模型
        "SiteConfig",
        "MemoryMonitor",
        # 组件
        "CacheManager",
        "ResilienceManager",
        "StatsCollector",
        # 适配器
        "SiteAdapter",
        "GenericSiteAdapter",
        "TorrentSiteAdapter",
        "MagnetLinkAdapter",
        "AdapterFactory",
        "AdaptiveParser",
        "SiteType",
        # 优化器
        "OptimizationLevel",
        "SmartConcurrencyController",
        "OptimizedAsyncWebCrawler",
        "PerformanceOptimizer",
    ]
except ImportError as e:
    __all__ = ["WebCrawler"]
    import warnings
    warnings.warn(f"WebCrawler新模块导入失败: {e}", UserWarning)

# 版本信息
from ..__version__ import __version__ as __project_version__
__version__ = __project_version__
__author__ = "qBittorrent Monitor Team"
