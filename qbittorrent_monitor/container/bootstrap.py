"""应用启动引导

初始化所有依赖并注册到容器。
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from .container import get_container, Container
from ..config import Config, load_config
from ..core import MagnetProcessor, DebounceService, PacingService

if TYPE_CHECKING:
    from ..database import DatabaseManager


async def bootstrap(config: Optional[Config] = None) -> Container:
    """初始化应用依赖
    
    Args:
        config: 配置对象，如果为 None 则自动加载
        
    Returns:
        配置好的容器
    """
    # 延迟导入避免循环依赖
    from ..database import DatabaseManager
    from ..repository import TorrentRepository, StatsRepository, EventRepository
    from ..services import HistoryService, MetricsService
    from ..qb_client import QBClient
    from ..classifier import ContentClassifier
    
    container = get_container()
    
    # 配置
    if config is None:
        config = load_config()
    container.register_instance(Config, config)
    
    # 核心组件
    container.register_instance(MagnetProcessor, MagnetProcessor())
    container.register_factory(
        DebounceService,
        lambda: DebounceService(debounce_seconds=config.check_interval)
    )
    container.register_factory(
        PacingService,
        lambda: PacingService()
    )
    
    # 指标服务（非全局）
    metrics = MetricsService(enabled=config.metrics.enabled)
    container.register_instance(MetricsService, metrics)
    
    # 数据库相关（如果启用）
    if config.database.enabled:
        db = DatabaseManager(config.database.db_path)
        await db.initialize()
        container.register_instance(DatabaseManager, db)
        
        # Repository
        container.register_factory(
            TorrentRepository,
            lambda: TorrentRepository(db.connection)
        )
        container.register_factory(
            StatsRepository,
            lambda: StatsRepository(db.connection)
        )
        container.register_factory(
            EventRepository,
            lambda: EventRepository(db.connection)
        )
        
        # 服务
        container.register_factory(
            HistoryService,
            lambda: HistoryService(
                torrent_repo=container.resolve(TorrentRepository),
                stats_repo=container.resolve(StatsRepository),
                event_repo=container.resolve(EventRepository),
                magnet_processor=container.resolve(MagnetProcessor)
            )
        )
    
    # QBClient
    container.register_factory(
        QBClient,
        lambda: QBClient(config)
    )
    
    # 分类器
    container.register_factory(
        ContentClassifier,
        lambda: ContentClassifier(config)
    )
    
    return container


def bootstrap_sync(config: Optional[Config] = None) -> Container:
    """同步初始化（用于非异步环境）"""
    import asyncio
    return asyncio.run(bootstrap(config))
