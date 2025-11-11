"""
增强的qBittorrent客户端模块（重构版）
支持模块化架构
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any

from .connection_pool import ConnectionPoolManager
from .cache_manager import CacheManager
from .api_client import APIClient
from .torrent_manager import TorrentManager
from .category_manager import CategoryManager
from .metrics import MetricsCollector
from .batch_operations import BatchOperations

from ..config import QBittorrentConfig, AppConfig
from ..resilience import RateLimiter, CircuitBreaker
from ..exceptions import QBittorrentError


class QBittorrentClient:
    """增强的异步qBittorrent API客户端（模块化架构）"""
    
    def __init__(self, config: QBittorrentConfig, app_config: Optional[AppConfig] = None):
        self.config = config
        self.app_config = app_config
        self.logger = logging.getLogger('QBittorrentClient')
        
        self._base_url = f"{'https' if config.use_https else 'http'}://{config.host}:{config.port}"
        self._connection_pool_size = getattr(config, 'connection_pool_size', 10)
        self._cache_ttl = getattr(config, 'cache_ttl_seconds', 300)
        self._cache_max_size = getattr(config, 'cache_max_size', 1000)
        
        # 初始化组件
        self._initialize_components()
        self._pool: Optional[ConnectionPoolManager] = None
        self._is_cleaned_up = False
        self._cleanup_lock = asyncio.Lock()
    
    def _initialize_components(self):
        """初始化所有组件"""
        self._cache = CacheManager(max_size=self._cache_max_size, ttl_seconds=self._cache_ttl)
        self._metrics = MetricsCollector()
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=getattr(self.config, 'circuit_breaker_threshold', 5),
            recovery_timeout=getattr(self.config, 'circuit_breaker_timeout', 60),
            on_state_change=self._on_circuit_state_change,
        )
        self._rate_limiter = RateLimiter(getattr(self.config, 'max_requests_per_minute', 60))
        
        self._api_client: Optional[APIClient] = None
        self._torrent_manager: Optional[TorrentManager] = None
        self._category_manager: Optional[CategoryManager] = None
    
    async def init(self):
        """初始化客户端"""
        await self._cache.init()
        await self._metrics.init()
        
        self._api_client = APIClient(
            base_url=self._base_url,
            username=self.config.username,
            password=self.config.password,
            rate_limiter=self._rate_limiter,
            circuit_breaker=self._circuit_breaker,
            cache_manager=self._cache,
            metrics=self._metrics
        )
        
        if not await self._api_client.login():
            raise QBittorrentError("qBittorrent登录失败")
        
        self._torrent_manager = TorrentManager(self._api_client)
        self._category_manager = CategoryManager(self._api_client)
    
    async def close(self):
        """关闭客户端"""
        await self.cleanup()
    
    async def cleanup(self):
        """清理所有资源"""
        async with self._cleanup_lock:
            if self._is_cleaned_up:
                return
            
            try:
                if self._pool:
                    await self._pool.close_all()
                if hasattr(self, '_cache'):
                    await self._cache.clear()
                self._is_cleaned_up = True
            except Exception as e:
                self.logger.error(f"清理资源时出错: {e}")
                self._is_cleaned_up = True
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.init()
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        """异步上下文管理器退出"""
        await self.cleanup()
    
    def _on_circuit_state_change(self, state: str):
        """断路器状态变化回调"""
        if state == 'open':
            self.logger.warning("断路器已打开")
        elif state == 'half_open':
            self.logger.info("断路器进入半开状态")
        elif state == 'closed':
            self.logger.info("断路器恢复")
    
    # 代理方法
    async def add_torrent(self, magnet_link: str, category: str, **kwargs) -> bool:
        if not self._torrent_manager:
            raise QBittorrentError("客户端未初始化")
        return await self._torrent_manager.add_torrent(magnet_link, category, **kwargs)
    
    async def get_torrents(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._torrent_manager:
            raise QBittorrentError("客户端未初始化")
        return await self._torrent_manager.get_torrents(category)
    
    async def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        if not self._torrent_manager:
            raise QBittorrentError("客户端未初始化")
        return await self._torrent_manager.delete_torrent(torrent_hash, delete_files)
    
    async def pause_torrent(self, torrent_hash: str) -> bool:
        if not self._torrent_manager:
            raise QBittorrentError("客户端未初始化")
        return await self._torrent_manager.pause_torrent(torrent_hash)
    
    async def resume_torrent(self, torrent_hash: str) -> bool:
        if not self._torrent_manager:
            raise QBittorrentError("客户端未初始化")
        return await self._torrent_manager.resume_torrent(torrent_hash)
    
    async def get_torrent_properties(self, torrent_hash: str) -> Dict[str, Any]:
        if not self._torrent_manager:
            raise QBittorrentError("客户端未初始化")
        return await self._torrent_manager.get_torrent_properties(torrent_hash)
    
    async def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        if not self._torrent_manager:
            raise QBittorrentError("客户端未初始化")
        return await self._torrent_manager.get_torrent_files(torrent_hash)
    
    async def get_existing_categories(self) -> Dict[str, Dict[str, Any]]:
        if not self._category_manager:
            raise QBittorrentError("客户端未初始化")
        return await self._category_manager.get_existing_categories()
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            'performance': self._metrics.get_performance_stats(),
            'cache': self._cache.get_stats(),
            'circuit_breaker': self._circuit_breaker.get_state()
        }


class OptimizedQBittorrentClient(QBittorrentClient):
    """优化版qBittorrent客户端"""
    
    def __init__(self, config: QBittorrentConfig, app_config: Optional[AppConfig] = None):
        super().__init__(config, app_config)
        self._batch_operations: Optional[BatchOperations] = None
    
    async def init(self):
        await super().init()
        self._batch_operations = BatchOperations(
            api_client=self._api_client,
            torrent_manager=self._torrent_manager,
            max_workers=4
        )
    
    async def add_torrents_batch(self, magnet_links: List[str], category: str, **kwargs) -> Dict[str, bool]:
        if not self._batch_operations:
            raise QBittorrentError("客户端未初始化")
        return await self._batch_operations.add_torrents_batch(magnet_links, category, **kwargs)
    
    async def get_torrents_batch(self, categories: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
        if not self._batch_operations:
            raise QBittorrentError("客户端未初始化")
        return await self._batch_operations.get_torrents_batch(categories)
    
    def get_batch_stats(self) -> Dict[str, Any]:
        if not self._batch_operations:
            return {}
        return self._batch_operations.get_batch_stats()
