"""连接池管理 - 支持单级和多级连接池

此模块提供连接池管理功能，包括单级连接池和多级连接池，
用于优化HTTP连接性能。
"""

import asyncio
import logging
from typing import List, Optional

import aiohttp


logger = logging.getLogger(__name__)


class ConnectionPool:
    """单级连接池 - 基础连接管理
    
    管理多个HTTP会话，使用轮询方式分配连接。
    
    Attributes:
        pool_size: 连接池大小
        timeout: 连接超时设置
        sessions: HTTP会话列表
    
    Example:
        >>> pool = ConnectionPool(pool_size=10)
        >>> await pool.initialize()
        >>> session = await pool.get_session()
    """
    
    def __init__(self, pool_size: int = 10, timeout_seconds: int = 30):
        """初始化连接池
        
        Args:
            pool_size: 连接池大小
            timeout_seconds: 超时时间（秒）
        """
        self.pool_size = pool_size
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds, connect=10)
        self.sessions: List[aiohttp.ClientSession] = []
        self._session_index = 0
        self._session_lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self) -> None:
        """初始化连接池"""
        if self._initialized:
            return
            
        for i in range(self.pool_size):
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            session = aiohttp.ClientSession(
                timeout=self.timeout,
                connector=connector
            )
            self.sessions.append(session)
        
        self._initialized = True
        logger.info(f"连接池初始化完成: {self.pool_size} 个会话")
    
    async def get_session(self) -> aiohttp.ClientSession:
        """获取下一个可用会话（轮询）
        
        Returns:
            HTTP会话
        
        Raises:
            RuntimeError: 连接池未初始化
        """
        if not self._initialized:
            await self.initialize()
        
        async with self._session_lock:
            if not self.sessions:
                raise RuntimeError("连接池未初始化")
            session = self.sessions[self._session_index]
            self._session_index = (self._session_index + 1) % len(self.sessions)
            return session
    
    async def close_all(self) -> None:
        """关闭所有会话"""
        async with self._session_lock:
            for i, session in enumerate(self.sessions):
                if session and not session.closed:
                    await session.close()
                    logger.debug(f"关闭会话 {i+1}/{len(self.sessions)}")
            self.sessions.clear()
            self._initialized = False
            await asyncio.sleep(0.5)  # 等待关闭完成
        logger.info("连接池已关闭")


class MultiTierConnectionPool:
    """多级连接池 - 读写API分离
    
    分离读写操作到不同的连接池，优化性能。
    
    Attributes:
        read_pool_size: 读连接池大小
        write_pool_size: 写连接池大小
        api_pool_size: API连接池大小
    
    Example:
        >>> pool = MultiTierConnectionPool(read_pool_size=10, write_pool_size=5)
        >>> await pool.initialize()
        >>> session = pool.read_pool
    """
    
    def __init__(
        self,
        read_pool_size: int = 10,
        write_pool_size: int = 5,
        api_pool_size: int = 20,
        timeout_seconds: int = 30
    ):
        """初始化多级连接池
        
        Args:
            read_pool_size: 读连接池大小
            write_pool_size: 写连接池大小
            api_pool_size: API连接池大小
            timeout_seconds: 超时时间（秒）
        """
        self.read_pool_size = read_pool_size
        self.write_pool_size = write_pool_size
        self.api_pool_size = api_pool_size
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds, connect=10)
        
        self._read_pool: Optional[aiohttp.ClientSession] = None
        self._write_pool: Optional[aiohttp.ClientSession] = None
        self._api_pool: Optional[aiohttp.ClientSession] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """初始化多级连接池"""
        if self._initialized:
            return
            
        # 读连接池
        read_connector = aiohttp.TCPConnector(
            limit=self.read_pool_size,
            limit_per_host=5,
            keepalive_timeout=30
        )
        self._read_pool = aiohttp.ClientSession(
            timeout=self.timeout,
            connector=read_connector
        )
        
        # 写连接池
        write_connector = aiohttp.TCPConnector(
            limit=self.write_pool_size,
            limit_per_host=3,
            keepalive_timeout=30
        )
        self._write_pool = aiohttp.ClientSession(
            timeout=self.timeout,
            connector=write_connector
        )
        
        # API连接池
        api_connector = aiohttp.TCPConnector(
            limit=self.api_pool_size,
            limit_per_host=10,
            keepalive_timeout=60
        )
        self._api_pool = aiohttp.ClientSession(
            timeout=self.timeout,
            connector=api_connector
        )
        
        self._initialized = True
        logger.info(
            f"多级连接池初始化完成: "
            f"读({self.read_pool_size}) 写({self.write_pool_size}) API({self.api_pool_size})"
        )
    
    @property
    def read_pool(self) -> aiohttp.ClientSession:
        """获取读连接池"""
        if self._read_pool is None:
            raise RuntimeError("连接池未初始化")
        return self._read_pool
    
    @property
    def write_pool(self) -> aiohttp.ClientSession:
        """获取写连接池"""
        if self._write_pool is None:
            raise RuntimeError("连接池未初始化")
        return self._write_pool
    
    @property
    def api_pool(self) -> aiohttp.ClientSession:
        """获取API连接池"""
        if self._api_pool is None:
            raise RuntimeError("连接池未初始化")
        return self._api_pool
    
    async def close_all(self) -> None:
        """关闭所有连接池"""
        pools = [
            (self._read_pool, "读连接池"),
            (self._write_pool, "写连接池"),
            (self._api_pool, "API连接池")
        ]
        for pool, name in pools:
            if pool and not pool.closed:
                await pool.close()
                logger.debug(f"{name}已关闭")
        
        self._read_pool = None
        self._write_pool = None
        self._api_pool = None
        self._initialized = False
        logger.info("多级连接池已关闭")
