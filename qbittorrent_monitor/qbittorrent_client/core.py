"""qBittorrent客户端核心模块

此模块提供 QBittorrentClient 类，实现qBittorrent客户端的核心功能。
"""

from __future__ import annotations

import asyncio
import logging
import random
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, TypeVar

import aiohttp

from .cache_manager import CacheManager

if TYPE_CHECKING:
    from ..config import Config


logger = logging.getLogger(__name__)
T = TypeVar('T')


class APIErrorType(Enum):
    """API错误类型枚举"""
    NETWORK_ERROR = "network_error"
    AUTH_ERROR = "auth_error"
    API_ERROR = "api_error"
    TIMEOUT_ERROR = "timeout_error"
    SERVER_ERROR = "server_error"


class QBAPIError(Exception):
    """API调用错误 - 包含详细错误信息"""
    
    def __init__(
        self,
        message: str,
        error_type: APIErrorType,
        status_code: Optional[int] = None,
        endpoint: Optional[str] = None,
        retry_count: int = 0
    ):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
        self.endpoint = endpoint
        self.retry_count = retry_count
    
    def __str__(self) -> str:
        parts = [self.args[0]]
        if self.endpoint:
            parts.append(f"endpoint={self.endpoint}")
        if self.status_code:
            parts.append(f"status={self.status_code}")
        if self.retry_count > 0:
            parts.append(f"retries={self.retry_count}")
        return f"[{self.error_type.value}] " + " | ".join(parts)


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    retry_on: Optional[tuple] = None
) -> Callable:
    """指数退避重试装饰器
    
    Args:
        max_retries: 最大重试次数
        base_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数基数
        retry_on: 需要重试的异常类型元组
    
    Returns:
        装饰器函数
    """
    if retry_on is None:
        retry_on = (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            Exception,
        )
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_on as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        # 计算指数退避延迟（添加抖动）
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        # 添加随机抖动 (±20%)
                        jitter = delay * 0.2 * (2 * random.random() - 1)
                        sleep_time = delay + jitter
                        
                        func_name = func.__name__
                        logger.warning(
                            f"{func_name} 第 {attempt + 1}/{max_retries + 1} 次尝试失败，"
                            f"{sleep_time:.2f}秒后重试..."
                        )
                        await asyncio.sleep(sleep_time)
                    else:
                        logger.error(
                            f"{func.__name__} 在 {max_retries + 1} 次尝试后仍然失败"
                        )
            
            # 重试耗尽，抛出异常
            raise last_exception
        
        return wrapper
    return decorator


class QBittorrentClient:
    """改进的异步qBittorrent客户端
    
    提供与qBittorrent Web API的交互，包括：
    - 认证管理
    - 种子添加
    - 分类管理
    - 缓存支持
    
    Attributes:
        config: 应用配置
        base_url: API基础URL
        session: HTTP会话
        cache: 缓存管理器
    
    Example:
        >>> from qbittorrent_monitor.qbittorrent_client import QBittorrentClient
        >>> client = QBittorrentClient(config)
        >>> async with client:
        ...     await client.add_torrent(magnet, category="movies")
    """
    
    # HTTP 状态码分类
    HTTP_OK = 200
    HTTP_UNAUTHORIZED = 401
    HTTP_FORBIDDEN = 403
    HTTP_NOT_FOUND = 404
    HTTP_SERVER_ERROR_START = 500
    
    def __init__(
        self,
        config: Config,
        cache: Optional[CacheManager] = None
    ):
        """初始化客户端
        
        Args:
            config: 应用配置
            cache: 缓存管理器（可选）
        """
        self.config = config
        self.qb_config = config.qbittorrent
        self.base_url = self._build_base_url()
        self.session: Optional[aiohttp.ClientSession] = None
        self._is_authenticated = False
        self.cache = cache or CacheManager()
    
    def _build_base_url(self) -> str:
        """构建基础URL"""
        protocol = "https" if self.qb_config.use_https else "http"
        return f"{protocol}://{self.qb_config.host}:{self.qb_config.port}"
    
    def _get_full_url(self, endpoint: str) -> str:
        """获取完整API URL"""
        return f"{self.base_url}/api/v2{endpoint}"
    
    def _create_session(self) -> aiohttp.ClientSession:
        """创建配置了超时和连接池的HTTP会话"""
        timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=10)
        connector = aiohttp.TCPConnector(
            limit=10,
            limit_per_host=5,
            enable_cleanup_closed=True,
            force_close=False,
            ssl=False if not self.qb_config.use_https else None,
        )
        
        headers = {
            'User-Agent': 'qBittorrent-Monitor/1.0',
        }
        # 添加 Referer 头以通过 qBittorrent CSRF 保护
        headers['Referer'] = self.base_url
        
        # 创建 cookie jar，unsafe=True 允许 IP 地址的 cookie
        cookie_jar = aiohttp.CookieJar(unsafe=True)
        
        return aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            raise_for_status=False,
            headers=headers,
            cookie_jar=cookie_jar,
        )
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = self._create_session()
        await self.login()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self.session:
            await self.session.close()
            self.session = None
        self._is_authenticated = False
    
    def _handle_response_error(
        self,
        response: aiohttp.ClientResponse,
        endpoint: str,
        retry_count: int = 0
    ) -> None:
        """处理HTTP响应错误"""
        status = response.status
        
        if status == self.HTTP_UNAUTHORIZED or status == self.HTTP_FORBIDDEN:
            error_msg = f"认证失败: 无效的凭据或会话已过期 (status={status})"
            logger.error(f"{error_msg} [endpoint={endpoint}]")
            raise QBAPIError(
                error_msg,
                APIErrorType.AUTH_ERROR,
                status_code=status,
                endpoint=endpoint,
                retry_count=retry_count
            )
        
        elif status == self.HTTP_NOT_FOUND:
            error_msg = f"API端点不存在: {endpoint} (status={status})"
            logger.error(error_msg)
            raise QBAPIError(
                error_msg,
                APIErrorType.API_ERROR,
                status_code=status,
                endpoint=endpoint,
                retry_count=retry_count
            )
        
        elif status >= self.HTTP_SERVER_ERROR_START:
            error_msg = f"服务器内部错误 (status={status})"
            logger.error(f"{error_msg} [endpoint={endpoint}]")
            raise QBAPIError(
                error_msg,
                APIErrorType.SERVER_ERROR,
                status_code=status,
                endpoint=endpoint,
                retry_count=retry_count
            )
        
        elif status != self.HTTP_OK:
            error_msg = f"API调用失败 (status={status})"
            logger.error(f"{error_msg} [endpoint={endpoint}]")
            raise QBAPIError(
                error_msg,
                APIErrorType.API_ERROR,
                status_code=status,
                endpoint=endpoint,
                retry_count=retry_count
            )
    
    @with_retry(max_retries=3, base_delay=1.0)
    async def login(self) -> None:
        """登录获取cookie"""
        if self.session is None:
            self.session = self._create_session()
        
        endpoint = "/auth/login"
        url = self._get_full_url(endpoint)
        
        data = {
            "username": self.qb_config.username,
            "password": self.qb_config.password
        }
        
        logger.debug(f"尝试登录到 qBittorrent: {self.base_url}")
        
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == self.HTTP_OK:
                    result = await resp.text()
                    if result == "Ok.":
                        logger.info(f"qBittorrent登录成功: {self.base_url}")
                        self._is_authenticated = True
                    else:
                        error_msg = f"登录失败: 服务器返回 '{result}'"
                        logger.error(error_msg)
                        raise QBAPIError(error_msg, APIErrorType.AUTH_ERROR)
                else:
                    self._handle_response_error(resp, endpoint)
        
        except aiohttp.ClientConnectorError as e:
            error_msg = "无法连接到qBittorrent服务器"
            logger.error(f"{error_msg}: {e}")
            raise QBAPIError(error_msg, APIErrorType.NETWORK_ERROR)
        
        except asyncio.TimeoutError:
            error_msg = "登录请求超时"
            logger.error(error_msg)
            raise QBAPIError(error_msg, APIErrorType.TIMEOUT_ERROR)
    
    async def _ensure_authenticated(self) -> None:
        """确保已认证，如果未认证则重新登录"""
        if not self._is_authenticated:
            logger.warning("会话未认证，尝试重新登录...")
            await self.login()
    
    @with_retry(max_retries=3, base_delay=0.5)
    async def add_torrent(
        self,
        magnet: str,
        category: Optional[str] = None,
        save_path: Optional[str] = None
    ) -> bool:
        """添加磁力链接
        
        Args:
            magnet: 磁力链接
            category: 分类名称（可选）
            save_path: 保存路径（可选）
        
        Returns:
            是否添加成功
        """
        await self._ensure_authenticated()
        
        endpoint = "/torrents/add"
        url = self._get_full_url(endpoint)
        
        data: Dict[str, Any] = {"urls": magnet}
        if category:
            data["category"] = category
        if save_path:
            data["savepath"] = save_path
        
        logger.info(f"正在添加种子: category={category}")
        
        try:
            async with self.session.post(url, data=data) as resp:
                self._handle_response_error(resp, endpoint)
                result_text = await resp.text()
                logger.info(f"种子添加成功 [category={category}]")
                return True
        
        except QBAPIError as e:
            logger.error(f"添加种子失败: {e}")
            return False
        
        except Exception as e:
            logger.exception(f"添加种子时发生未知错误")
            return False
    
    @with_retry(max_retries=3, base_delay=0.5)
    async def get_categories(self) -> Dict[str, Any]:
        """获取所有分类
        
        Returns:
            分类字典，失败时返回空字典
        """
        await self._ensure_authenticated()
        
        # 检查缓存
        cache_key = "categories"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        endpoint = "/torrents/categories"
        url = self._get_full_url(endpoint)
        
        try:
            async with self.session.get(url) as resp:
                self._handle_response_error(resp, endpoint)
                categories = await resp.json()
                logger.debug(f"获取到 {len(categories)} 个分类")
                # 缓存结果
                self.cache.set(cache_key, categories)
                return categories
        
        except QBAPIError:
            logger.error("获取分类列表失败")
            return {}
        
        except Exception as e:
            logger.exception(f"获取分类时发生错误")
            return {}
    
    @with_retry(max_retries=3, base_delay=0.5)
    async def create_category(self, name: str, save_path: str) -> bool:
        """创建分类
        
        Args:
            name: 分类名称
            save_path: 保存路径
        
        Returns:
            是否创建成功
        """
        await self._ensure_authenticated()
        
        endpoint = "/torrents/createCategory"
        url = self._get_full_url(endpoint)
        
        data = {"category": name, "savePath": save_path}
        logger.info(f"正在创建分类: name={name}")
        
        try:
            async with self.session.post(url, data=data) as resp:
                self._handle_response_error(resp, endpoint)
                logger.info(f"分类创建成功: {name}")
                # 清除缓存
                self.cache.clear()
                return True
        
        except QBAPIError as e:
            logger.error(f"创建分类失败 [{name}]: {e}")
            return False
        
        except Exception as e:
            logger.exception(f"创建分类时发生未知错误 [{name}]")
            return False
    
    async def ensure_categories(self) -> None:
        """确保配置中的分类都存在"""
        logger.info("检查并创建必要的分类...")
        
        existing = await self.get_categories()
        categories_to_create = []
        
        if hasattr(self.config, 'categories'):
            for name, cat in self.config.categories.items():
                if name not in existing:
                    categories_to_create.append((name, cat.save_path))
        
        if not categories_to_create:
            logger.info("所有分类已存在，无需创建")
            return
        
        logger.info(f"需要创建 {len(categories_to_create)} 个分类")
        
        created_count = 0
        for name, save_path in categories_to_create:
            if await self.create_category(name, save_path):
                created_count += 1
        
        logger.info(f"分类创建完成: {created_count}/{len(categories_to_create)} 成功")
    
    async def cleanup(self) -> None:
        """清理资源"""
        if self.session:
            await self.session.close()
            self.session = None
        self._is_authenticated = False
        self.cache.clear()
        logger.debug("QBittorrentClient 资源已清理")
