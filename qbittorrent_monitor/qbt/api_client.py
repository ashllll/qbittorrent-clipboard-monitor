"""
API客户端核心

处理HTTP请求和响应，包括：
- 带重试的HTTP请求
- 断路器模式
- 速率限制
- 错误处理
- 性能统计
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
import aiohttp
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class APIClient:
    """API客户端核心类"""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        rate_limiter,
        circuit_breaker,
        cache_manager,
        metrics
    ):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.rate_limiter = rate_limiter
        self.circuit_breaker = circuit_breaker
        self.cache_manager = cache_manager
        self.metrics = metrics
        self._authenticated = False

        logger.debug(f"API客户端初始化: {base_url}")

    async def login(self) -> bool:
        """登录qBittorrent"""
        try:
            # 发送登录请求
            data = {
                'username': self.username,
                'password': self.password
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/v2/auth/login",
                    data=data
                ) as response:
                    if response.status == 200:
                        self._authenticated = True
                        logger.info("qBittorrent登录成功")
                        return True
                    else:
                        logger.error(f"qBittorrent登录失败: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"登录qBittorrent时出错: {e}")
            return False

    async def request(
        self,
        method: str,
        endpoint: str,
        params: dict = None,
        data: dict = None,
        use_cache: bool = True
    ) -> Tuple[int, Any]:
        """
        发送HTTP请求
        
        Args:
            method: HTTP方法 (GET, POST, DELETE等)
            endpoint: API端点
            params: URL参数
            data: 请求体数据
            use_cache: 是否使用缓存
            
        Returns:
            (status_code, response_data)
        """
        start_time = time.time()
        url = f"{self.base_url}/api/v2/{endpoint}"

        try:
            # 检查速率限制
            if not self.rate_limiter.allow():
                raise Exception("API请求频率超限")

            # 检查断路器
            if not self.circuit_breaker.allow():
                raise Exception("服务暂时不可用（断路器打开）")

            # 生成缓存键
            cache_key = self.cache_manager._generate_cache_key(method, url, params, data)

            # 尝试从缓存获取
            if use_cache:
                cached_response = await self.cache_manager.get(cache_key)
                if cached_response is not None:
                    return cached_response

            # 发送请求
            async with aiohttp.ClientSession() as session:
                if data:
                    # POST请求发送表单数据
                    async with session.request(
                        method,
                        url,
                        params=params,
                        data=data
                    ) as response:
                        response_data = await self._parse_response(response)
                else:
                    # GET/DELETE等请求
                    async with session.request(
                        method,
                        url,
                        params=params
                    ) as response:
                        response_data = await self._parse_response(response)

            # 记录成功
            self.circuit_breaker.record_success()
            self.metrics.inc('requests')
            elapsed = time.time() - start_time
            self.metrics.record_response_time(elapsed)

            # 缓存响应
            if use_cache and response.status == 200:
                await self.cache_manager.set(cache_key, (response.status, response_data))

            return response.status, response_data

        except Exception as e:
            # 记录失败
            self.circuit_breaker.record_failure()
            self.metrics.inc('errors')
            elapsed = time.time() - start_time
            self.metrics.record_response_time(elapsed)
            
            logger.error(f"API请求失败: {method} {url} - {e}")
            raise

    async def _parse_response(self, response: aiohttp.ClientResponse) -> Any:
        """解析响应"""
        content_type = response.headers.get('content-type', '')

        if 'application/json' in content_type:
            return await response.json()
        elif 'text' in content_type:
            text = await response.text()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        else:
            # 二进制数据或其他类型
            return await response.read()

    async def get(self, endpoint: str, params: dict = None) -> Tuple[int, Any]:
        """GET请求"""
        return await self.request('GET', endpoint, params=params)

    async def post(self, endpoint: str, data: dict = None, params: dict = None) -> Tuple[int, Any]:
        """POST请求"""
        return await self.request('POST', endpoint, params=params, data=data)

    async def delete(self, endpoint: str, params: dict = None) -> Tuple[int, Any]:
        """DELETE请求"""
        return await self.request('DELETE', endpoint, params=params)

    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return self._authenticated
