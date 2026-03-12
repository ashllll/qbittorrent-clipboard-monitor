"""OpenAI SDK 连接池管理器

为 OpenAI 兼容的 AI 分类器提供客户端连接池管理，
支持多客户端轮询和统计监控。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ConnectionPoolManager(Generic[T]):
    """OpenAI SDK 连接池管理器

    管理多个 AI 客户端实例，提供轮询分发和统一清理功能。
    适用于 DeepSeek、OpenAI 等兼容 OpenAI SDK 的 API。

    Attributes:
        factory: 客户端工厂函数，返回 T 类型的客户端实例
        pool_size: 连接池大小（默认 3）

    Example:
        >>> def create_client():
        ...     return OpenAI(api_key="sk-...", base_url="https://api.example.com")
        >>> pool = ConnectionPoolManager(create_client, pool_size=3)
        >>> pool.initialize()
        >>> client = pool.get_next()
        >>> # 使用客户端...
        >>> asyncio.run(pool.cleanup())
    """

    def __init__(
        self,
        factory: Callable[[], T],
        pool_size: int = 3,
    ):
        """初始化连接池管理器

        Args:
            factory: 客户端工厂函数
            pool_size: 连接池大小
        """
        self._factory = factory
        self._pool_size = pool_size
        self._pool: List[T] = []
        self._current_index = 0
        self._initialized = False
        self._lock = asyncio.Lock()
        self._stats = {
            "created": 0,
            "errors": 0,
            "requests": 0,
        }

    def initialize(self) -> None:
        """初始化连接池

        使用工厂函数创建所有客户端实例。
        如果已初始化，此方法不执行任何操作。

        Raises:
            Exception: 当工厂函数抛出异常时
        """
        if self._initialized:
            return

        for i in range(self._pool_size):
            try:
                client = self._factory()
                self._pool.append(client)
                self._stats["created"] += 1
                logger.debug(f"创建客户端实例 {i + 1}/{self._pool_size}")
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(f"创建客户端实例失败: {e}")
                raise

        self._initialized = True
        logger.debug(f"连接池初始化完成，大小: {len(self._pool)}")

    def get_next(self) -> Optional[T]:
        """获取下一个可用客户端（轮询）

        Returns:
            T: 客户端实例，如果未初始化则返回 None

        Example:
            >>> client = pool.get_next()
            >>> if client:
            ...     response = client.chat.completions.create(...)
        """
        if not self._initialized or not self._pool:
            return None

        client = self._pool[self._current_index]
        self._current_index = (self._current_index + 1) % len(self._pool)
        self._stats["requests"] += 1
        return client

    async def cleanup(self) -> None:
        """清理连接池

        异步关闭所有客户端连接。建议在程序退出时调用。

        Example:
            >>> async def main():
            ...     pool.initialize()
            ...     # 使用连接池...
            ...     await pool.cleanup()
        """
        if not self._initialized:
            return

        async with self._lock:
            for i, client in enumerate(self._pool):
                try:
                    # OpenAI 客户端有 close 方法
                    if hasattr(client, "close") and callable(getattr(client, "close")):
                        if asyncio.iscoroutinefunction(client.close):
                            await client.close()
                        else:
                            client.close()
                    logger.debug(f"关闭客户端实例 {i + 1}/{len(self._pool)}")
                except Exception as e:
                    logger.warning(f"关闭客户端实例时出错: {e}")

            self._pool.clear()
            self._initialized = False
            self._current_index = 0
            logger.debug("连接池已清理")

    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息

        Returns:
            Dict 包含以下字段:
            - size: 当前连接池大小
            - pool_size: 配置的最大连接数
            - initialized: 是否已初始化
            - current_index: 当前轮询索引
            - requests: 总请求数
            - created: 成功创建的客户端数
            - errors: 创建失败的次数

        Example:
            >>> stats = pool.get_stats()
            >>> print(f"连接池大小: {stats['size']}/{stats['pool_size']}")
        """
        return {
            "size": len(self._pool),
            "pool_size": self._pool_size,
            "initialized": self._initialized,
            "current_index": self._current_index,
            "requests": self._stats["requests"],
            "created": self._stats["created"],
            "errors": self._stats["errors"],
        }

    def __len__(self) -> int:
        """返回当前连接池大小"""
        return len(self._pool)

    def __bool__(self) -> bool:
        """检查连接池是否已初始化且有可用连接"""
        return self._initialized and len(self._pool) > 0
