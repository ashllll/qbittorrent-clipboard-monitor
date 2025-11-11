"""
连接池管理器

管理HTTP会话和连接池，负责：
- HTTP会话的生命周期管理
- 连接池的轮询和负载均衡
- 会话复用和清理
"""

import asyncio
import logging
import aiohttp
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionPoolManager:
    """连接池管理器"""

    def __init__(
        self,
        host: str,
        port: int,
        pool_size: int = 10,
        timeout: int = 30,
        use_https: bool = False
    ):
        self.host = host
        self.port = port
        self.pool_size = pool_size
        self.timeout = timeout
        self.use_https = use_https

        self._sessions: List[aiohttp.ClientSession] = []
        self._session_index = 0
        self._session_lock = asyncio.Lock()
        self._is_cleaned_up = False
        self._cleanup_lock = asyncio.Lock()

        logger.debug(f"连接池管理器初始化: {pool_size} 个连接")

    async def create_pool(self) -> None:
        """创建连接池"""
        timeout = aiohttp.ClientTimeout(total=self.timeout, connect=10)

        async with self._session_lock:
            # 创建连接池中的会话，每个会话使用独立的connector
            for i in range(self.pool_size):
                try:
                    connector = aiohttp.TCPConnector(
                        limit=100,
                        limit_per_host=30,
                        keepalive_timeout=30,
                        enable_cleanup_closed=True
                    )
                    session = aiohttp.ClientSession(
                        timeout=timeout,
                        connector=connector
                    )
                    self._sessions.append(session)
                    logger.debug(f"创建会话 {i+1}/{self.pool_size}")
                except Exception as e:
                    logger.error(f"创建会话 {i+1} 失败: {e}")
                    raise

        logger.info(f"连接池创建完成: {len(self._sessions)} 个会话")

    async def get_session(self) -> Optional[aiohttp.ClientSession]:
        """获取下一个可用会话（轮询）"""
        async with self._session_lock:
            if not self._sessions:
                logger.warning("连接池为空")
                return None

            session = self._sessions[self._session_index]
            self._session_index = (self._session_index + 1) % len(self._sessions)
            return session

    async def close_all(self) -> None:
        """关闭所有会话"""
        async with self._cleanup_lock:
            if self._is_cleaned_up:
                logger.info("连接池已标记为清理，跳过重复清理")
                return

            try:
                async with self._session_lock:
                    logger.info(f"关闭连接池中的 {len(self._sessions)} 个会话")

                    for i, session in enumerate(self._sessions):
                        if session and not session.closed:
                            try:
                                await session.close()
                                logger.debug(f"会话 {i+1} 已关闭")
                            except Exception as e:
                                logger.debug(f"关闭会话 {i+1} 时出错: {e}")

                    self._sessions.clear()

                    # 等待异步关闭操作完成
                    await asyncio.sleep(0.1)

                self._is_cleaned_up = True
                logger.info("连接池已完全清理")

            except Exception as e:
                logger.error(f"清理连接池时出错: {e}")
                # 确保标记为已清理，即使出错
                self._is_cleaned_up = True

    def get_pool_status(self) -> dict:
        """获取连接池状态"""
        active_sessions = sum(1 for s in self._sessions if s and not s.closed)
        return {
            "total_sessions": len(self._sessions),
            "active_sessions": active_sessions,
            "pool_size": self.pool_size,
            "current_index": self._session_index,
            "is_cleaned_up": self._is_cleaned_up
        }
