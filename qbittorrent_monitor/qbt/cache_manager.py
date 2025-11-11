"""
缓存管理器

管理API响应缓存和性能优化，包括：
- LRU缓存实现
- 缓存键生成
- 缓存命中/未命中统计
- 缓存TTL管理
"""

import hashlib
import logging
from typing import Any, Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheManager:
    """缓存管理器"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._access_count: Dict[str, int] = {}
        self._lock = None  # 在使用时初始化
        self._hits = 0
        self._misses = 0

        logger.debug(f"缓存管理器初始化: 最大 {max_size} 项，TTL {ttl_seconds} 秒")

    async def init(self):
        """初始化锁"""
        import asyncio
        if self._lock is None:
            self._lock = asyncio.Lock()

    def _generate_cache_key(
        self,
        method: str,
        url: str,
        params: dict = None,
        data: dict = None
    ) -> str:
        """生成缓存键"""
        key_data = f"{method}:{url}"
        if params:
            key_data += f":params:{sorted(params.items())}"
        if data:
            key_data += f":data:{sorted(data.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def get(self, cache_key: str) -> Optional[Any]:
        """从缓存获取数据"""
        async with self._lock:
            # 检查缓存是否存在
            if cache_key not in self._cache:
                self._misses += 1
                logger.debug(f"缓存未命中: {cache_key[:20]}...")
                return None

            # 检查是否过期
            if self._is_expired(cache_key):
                await self._remove(cache_key)
                self._misses += 1
                logger.debug(f"缓存已过期: {cache_key[:20]}...")
                return None

            # 记录访问
            self._access_count[cache_key] = self._access_count.get(cache_key, 0) + 1
            self._hits += 1
            logger.debug(f"缓存命中: {cache_key[:20]}...")
            return self._cache[cache_key]

    async def set(self, cache_key: str, data: Any) -> None:
        """将数据放入缓存"""
        async with self._lock:
            # 检查是否需要清理空间
            if len(self._cache) >= self.max_size:
                await self._evict_lru()

            # 存储数据
            self._cache[cache_key] = data
            self._timestamps[cache_key] = datetime.now()
            self._access_count[cache_key] = 1

            logger.debug(f"缓存已设置: {cache_key[:20]}...")

    def _is_expired(self, cache_key: str) -> bool:
        """检查缓存是否过期"""
        if cache_key not in self._timestamps:
            return True

        elapsed = datetime.now() - self._timestamps[cache_key]
        return elapsed.total_seconds() > self.ttl_seconds

    async def _remove(self, cache_key: str) -> None:
        """移除缓存项"""
        self._cache.pop(cache_key, None)
        self._timestamps.pop(cache_key, None)
        self._access_count.pop(cache_key, None)

    async def _evict_lru(self) -> None:
        """清理最少使用的缓存项"""
        if not self._cache:
            return

        # 找到访问次数最少的键
        lru_key = min(self._access_count, key=self._access_count.get)
        await self._remove(lru_key)
        logger.debug(f"清理LRU缓存项: {lru_key[:20]}...")

    async def clear(self) -> None:
        """清空所有缓存"""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            self._access_count.clear()
            logger.info("缓存已清空")

    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 2),
            "ttl_seconds": self.ttl_seconds
        }
