"""
增强的qBittorrent客户端 - 集成所有健壮性功能

特性：
- 集成统一异常处理和重试机制
- 使用增强的缓存系统
- 使用资源管理上下文管理器
- 使用统一熔断器和限流
- 集成监控和指标
- 支持多级连接池
- 智能批量操作
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
import aiohttp

from .exceptions_enhanced import retry, get_retry_config, RetryConfig, TimeoutError
from .enhanced_cache import get_global_cache, MultiLevelCache
from .resource_manager import (
    BaseAsyncResource, AsyncResourcePool, managed_resource, get_global_tracker
)
from .concurrency import (
    AsyncThrottler, AsyncBatchProcessor, get_concurrency_config,
    async_throttle
)
from .monitoring import (
    get_metrics_collector, get_health_checker, get_health_checker,
    PerformanceMonitor
)
from .circuit_breaker import (
    get_global_traffic_controller, UnifiedCircuitBreaker, UnifiedRateLimiter,
    CircuitBreakerConfig, RateLimitConfig, RateLimitStrategy
)
from .config_enhanced import ConfigValidator

from .exceptions import (
    QBittorrentError, NetworkError, QbtAuthError,
    QbtRateLimitError, QbtPermissionError, TorrentParseError
)
from .utils import parse_magnet
from .config import QBittorrentConfig, CategoryConfig, AppConfig

logger = logging.getLogger(__name__)


class EnhancedQBittorrentClient(BaseAsyncResource):
    """
    增强的qBittorrent客户端

    集成所有健壮性功能的企业级客户端
    """

    def __init__(
        self,
        qbt_config: QBittorrentConfig,
        app_config: Optional[AppConfig] = None
    ):
        super().__init__(f"qbt_client_{id(self)}")
        self.qbt_config = qbt_config
        self.app_config = app_config

        # 基础配置
        self._base_url = f"{'https' if qbt_config.use_https else 'http'}://{qbt_config.host}:{qbt_config.port}"
        self._session: Optional[aiohttp.ClientSession] = None
        self._authenticated = False

        # 初始化增强模块
        self._init_enhanced_features()

        # 连接池配置
        self._connection_pool_size = getattr(qbt_config, 'connection_pool_size', 10)
        self._max_retries = getattr(qbt_config, 'max_retries', 3)

    def _init_enhanced_features(self):
        """初始化增强功能"""
        # 获取全局组件
        self._cache = get_global_cache()
        self._metrics = get_metrics_collector()
        self._health_checker = get_health_checker()
        self._traffic_controller = get_global_traffic_controller()
        self._tracker = get_global_tracker()
        self._performance_monitor = PerformanceMonitor(self._metrics)

        # 注册健康检查
        self._health_checker.register_check(
            f"qbittorrent_{self.resource_id}",
            self._check_health,
            critical=True
        )

        # 配置熔断器
        cb_config = CircuitBreakerConfig(
            failure_threshold=getattr(self.qbt_config, 'circuit_breaker_threshold', 5),
            success_threshold=3,
            timeout=60.0,
            name=f"qbt_{self.resource_id}"
        )
        self._circuit_breaker = self._traffic_controller.add_circuit_breaker(
            f"qbt_{self.resource_id}",
            cb_config
        )

        # 配置限流器
        rl_config = RateLimitConfig(
            rate=getattr(self.qbt_config, 'max_requests_per_minute', 60) / 60.0,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            name=f"qbt_{self.resource_id}"
        )
        self._rate_limiter = self._traffic_controller.add_rate_limiter(
            f"qbt_{self.resource_id}",
            rl_config
        )

        # 配置节流器
        concurrency_config = get_concurrency_config("normal")
        self._throttler = AsyncThrottler(concurrency_config['max_concurrent'])

        # 配置批处理器
        self._batch_processor = AsyncBatchProcessor(
            batch_size=10,
            max_wait_time=1.0,
            max_workers=concurrency_config['max_workers']
        )

    async def _do_close(self):
        """关闭资源"""
        if self._session and not self._session.closed:
            await self._session.close()
        self._authenticated = False
        logger.info(f"QBittorrent客户端已关闭: {self.resource_id}")

    async def _check_health(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if not self._session or self._session.closed:
                return {
                    "status": "critical",
                    "message": "Session not initialized"
                }

            if not self._authenticated:
                return {
                    "status": "warning",
                    "message": "Not authenticated"
                }

            # 尝试获取版本
            version = await self.get_version()
            return {
                "status": "healthy",
                "message": f"Connected (version: {version})",
                "version": version
            }
        except Exception as e:
            return {
                "status": "critical",
                "message": f"Health check failed: {str(e)}"
            }

    async def ensure_authenticated(self):
        """确保已认证"""
        if not self._session or self._session.closed:
            await self._initialize_session()

        if not self._authenticated:
            await self.login()

    async def _initialize_session(self):
        """初始化HTTP会话"""
        connector = aiohttp.TCPConnector(
            limit=self._connection_pool_size,
            limit_per_host=30,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )

        timeout = aiohttp.ClientTimeout(
            total=30,
            connect=10,
            sock_read=30
        )

        self._session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={'User-Agent': 'QBittorrent-Monitor/1.0'}
        )

        # 注册到资源跟踪器
        await self._tracker.register_resource(
            resource_id=f"session_{self.resource_id}",
            resource_type="http_session",
            resource=self._session,
            size_bytes=1024 * 1024,  # 1MB估算
            metadata={
                "host": self.qbt_config.host,
                "port": self.qbt_config.port,
                "use_https": self.qbt_config.use_https
            }
        )

    @retry(config=get_retry_config("qbittorrent"))
    async def login(self):
        """登录qBittorrent"""
        await self.ensure_authenticated()

        url = f"{self._base_url}/api/v2/auth/login"
        data = {
            'username': self.qbt_config.username,
            'password': self.qbt_config.password
        }

        try:
            logger.info(f"尝试登录qBittorrent: {self.qbt_config.host}:{self.qbt_config.port}")

            async with self._session.post(url, data=data) as resp:
                if resp.status == 200:
                    response_text = await resp.text()
                    if response_text == "Ok.":
                        self._authenticated = True
                        logger.info("成功登录qBittorrent")

                        # 记录指标
                        await self._metrics.record_counter(
                            "qbittorrent.login.success",
                            1.0
                        )
                        return
                    else:
                        raise QbtAuthError(f"登录失败: {response_text}")
                elif resp.status == 403:
                    raise QbtAuthError("登录失败: 用户名或密码错误")
                elif resp.status == 429:
                    raise QbtRateLimitError("登录失败: API请求过于频繁")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"登录失败: HTTP {resp.status} - {error_text}")

        except aiohttp.ClientError as e:
            await self._metrics.record_counter(
                "qbittorrent.login.error",
                1.0
            )
            raise NetworkError(f"网络连接失败: {str(e)}") from e

    @retry(config=get_retry_config("default"))
    async def get_version(self) -> str:
        """获取qBittorrent版本信息"""
        await self.ensure_authenticated()

        url = f"{self._base_url}/api/v2/app/version"

        start_time = time.time()
        async with self._session.get(url) as resp:
            response_time = (time.time() - start_time) * 1000

            # 记录性能指标
            await self._performance_monitor.track_request(
                endpoint="/app/version",
                duration_ms=response_time,
                success=resp.status == 200,
                status_code=resp.status
            )

            if resp.status == 200:
                version = await resp.text().strip()
                await self._metrics.record_gauge(
                    "qbittorrent.response_time_ms",
                    response_time,
                    labels={"endpoint": "version"}
                )
                return version
            else:
                raise QBittorrentError(f"获取版本失败: HTTP {resp.status}")

    async def get_existing_categories(self) -> Dict[str, Dict[str, Any]]:
        """获取现有的分类及其详细信息"""
        await self.ensure_authenticated()

        url = f"{self._base_url}/api/v2/torrents/categories"

        # 尝试从缓存获取
        cache_key = "qbittorrent:categories"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        try:
            async with self._session.get(url) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('Content-Type', '')
                    if 'application/json' not in content_type:
                        raise QBittorrentError(f"获取分类失败: 响应类型错误 ({content_type})")

                    response_text = await resp.text()
                    if not response_text.strip():
                        logger.warning("qBittorrent返回空的分类列表")
                        categories = {}
                    else:
                        categories = json.loads(response_text)
                        logger.info(f"获取到 {len(categories)} 个现有分类")

                    # 缓存结果
                    await self._cache.set(cache_key, categories, ttl=300)
                    return categories

                elif resp.status == 403:
                    raise QbtPermissionError("获取分类失败: 权限不足")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"获取分类失败: HTTP {resp.status} - {error_text}")

        except aiohttp.ClientError as e:
            raise NetworkError(f"获取分类失败: {str(e)}") from e
        except json.JSONDecodeError as e:
            raise QBittorrentError(f"解析分类响应失败: {str(e)}") from e

    async def ensure_categories(self, categories: Dict[str, CategoryConfig]):
        """确保所有分类存在，动态更新分类路径"""
        try:
            existing_categories = await self.get_existing_categories()

            async with async_throttle(self._throttler, "category_operations"):
                for name, config in categories.items():
                    mapped_path = self._map_save_path(config.save_path, name)
                    logger.info(f"处理分类: {name}, 映射路径: {mapped_path}")

                    if name not in existing_categories:
                        logger.info(f"创建新分类: {name}")
                        await self._create_category(name, mapped_path)
                    else:
                        # 动态更新分类路径
                        existing_path = existing_categories[name].get('savePath', '')
                        if existing_path != mapped_path:
                            logger.info(f"更新分类路径: {name} (当前路径: {existing_path} -> 新路径: {mapped_path})")
                            await self._update_category(name, mapped_path)
                        else:
                            logger.info(f"分类路径未变，跳过更新: {name} (路径: {existing_path})")

        except Exception as e:
            logger.error(f"分类管理失败: {str(e)}")
            # 不再抛出异常，允许程序继续运行
            logger.warning("分类管理失败，但程序将继续运行")

    async def _create_category(self, name: str, save_path: str):
        """创建新分类"""
        url = f"{self._base_url}/api/v2/torrents/createCategory"
        data = {'category': name, 'savePath': save_path}

        try:
            async with self._session.post(url, data=data) as resp:
                if resp.status == 200:
                    logger.info(f"创建分类成功: {name} -> {save_path}")
                elif resp.status == 409:
                    logger.warning(f"分类已存在: {name}")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"创建分类失败: {error_text}")

        except aiohttp.ClientError as e:
            raise NetworkError(f"创建分类网络错误: {str(e)}") from e

    async def _update_category(self, name: str, save_path: str):
        """更新现有分类"""
        url = f"{self._base_url}/api/v2/torrents/editCategory"
        data = {'category': name, 'savePath': save_path}

        try:
            async with self._session.post(url, data=data) as resp:
                if resp.status == 200:
                    logger.info(f"更新分类成功: {name} -> {save_path}")
                elif resp.status == 409:
                    # 如果更新失败，尝试先删除再创建
                    logger.warning(f"更新分类失败，尝试重新创建: {name}")
                    await self._delete_category(name)
                    await self._create_category(name, save_path)
                else:
                    error_text = await resp.text()
                    # 当更新分类失败时，尝试删除并重新创建
                    logger.warning(f"更新分类失败: {error_text}，尝试重新创建")
                    await self._delete_category(name)
                    await self._create_category(name, save_path)

        except aiohttp.ClientError as e:
            raise NetworkError(f"更新分类网络错误: {str(e)}") from e

    async def _delete_category(self, name: str):
        """删除分类"""
        url = f"{self._base_url}/api/v2/torrents/removeCategories"
        data = {'categories': name}

        try:
            async with self._session.post(url, data=data) as resp:
                if resp.status == 200:
                    logger.info(f"删除分类成功: {name}")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"删除分类失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"删除分类网络错误: {str(e)}") from e

    def _map_save_path(self, original_path: str, category_name: str = "") -> str:
        """增强的路径映射功能"""
        if not self.app_config:
            return original_path

        # 如果配置为直接使用NAS路径
        if self.app_config.use_nas_paths_directly or self.qbt_config.use_nas_paths_directly:
            return original_path

        # 优先使用新的路径映射规则
        if self.qbt_config.path_mapping:
            for mapping in self.qbt_config.path_mapping:
                if original_path.startswith(mapping.source_prefix):
                    mapped_path = original_path.replace(
                        mapping.source_prefix,
                        mapping.target_prefix,
                        1
                    )
                    logger.debug(
                        f"路径映射 ({mapping.description or 'N/A'}): "
                        f"{original_path} -> {mapped_path}"
                    )
                    return mapped_path

        # 回退到传统的全局路径映射
        for source, target in self.app_config.path_mapping.items():
            if original_path.startswith(source):
                mapped_path = original_path.replace(source, target, 1)
                logger.debug(f"全局路径映射: {original_path} -> {mapped_path}")
                return mapped_path

        # 没有匹配的规则，返回原始路径
        logger.debug(f"无路径映射规则匹配，使用原始路径: {original_path}")
        return original_path

    async def add_torrent(
        self,
        magnet_link: str,
        category: str,
        **kwargs
    ) -> bool:
        """添加磁力链接"""
        # 使用流量控制器
        return await self._traffic_controller.call(
            self._add_torrent_impl,
            circuit_breaker_name=f"qbt_{self.resource_id}",
            rate_limiter_name=f"qbt_{self.resource_id}",
            fallback=self._fallback_add_torrent,
            magnet_link=magnet_link,
            category=category,
            **kwargs
        )

    async def _add_torrent_impl(
        self,
        magnet_link: str,
        category: str,
        **kwargs
    ) -> bool:
        """实际的添加种子实现"""
        await self.ensure_authenticated()

        # 解析磁力链接
        torrent_hash, torrent_name = parse_magnet(magnet_link)
        if not torrent_hash:
            raise TorrentParseError("无效的磁力链接格式")

        # 如果磁力链接没有dn参数，尝试从种子属性获取名称
        display_name = torrent_name or f"磁力链接_{torrent_hash[:8]}"
        logger.debug(f"原始磁力链接文件名: {torrent_name}")

        # 检查是否重复
        if await self._is_duplicate(torrent_hash):
            logger.info(f"跳过重复种子: {display_name}")
            return False

        # 验证分类存在
        existing_categories = await self.get_existing_categories()

        url = f"{self._base_url}/api/v2/torrents/add"
        data = {
            'urls': magnet_link,
            'autoTMM': 'false',  # 关闭自动种子管理
            **kwargs
        }

        # 设置分类
        if category in existing_categories:
            data['category'] = category
            save_path = existing_categories[category]['savePath']
            logger.info(f"种子将添加到分类: {category} ({save_path})")
        else:
            logger.warning(f"分类不存在: {category}，将使用默认路径")

        # 限流控制
        async with async_throttle(self._throttler, "add_torrent"):
            start_time = time.time()
            async with self._session.post(url, data=data) as resp:
                response_time = (time.time() - start_time) * 1000

                # 记录性能指标
                await self._performance_monitor.track_request(
                    endpoint="/torrents/add",
                    duration_ms=response_time,
                    success=resp.status == 200,
                    status_code=resp.status
                )

                if resp.status == 200:
                    response_text = await resp.text()
                    if response_text != "Fails.":
                        # 种子添加成功
                        try:
                            await asyncio.sleep(1)
                            torrent_info = await self.get_torrent_properties(torrent_hash)
                            if 'name' in torrent_info and torrent_info['name']:
                                actual_name = torrent_info['name']
                                logger.info(f"成功添加种子: {actual_name}")
                            else:
                                logger.info(f"成功添加种子: {display_name}")
                        except Exception as e:
                            logger.warning(f"获取种子属性失败但不影响添加: {str(e)}")
                            logger.info(f"成功添加种子: {display_name}")

                        # 记录成功指标
                        await self._metrics.record_counter(
                            "qbittorrent.torrent.added",
                            1.0,
                            labels={"category": category}
                        )

                        return True
                    else:
                        raise QBittorrentError("添加种子失败: qBittorrent返回Fails")
                elif resp.status == 403:
                    raise QbtPermissionError("添加种子失败: 权限不足")
                elif resp.status == 429:
                    raise QbtRateLimitError("添加种子失败: API请求过于频繁")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"添加种子失败: HTTP {resp.status} - {error_text}")

    async def _fallback_add_torrent(
        self,
        magnet_link: str,
        category: str,
        **kwargs
    ) -> bool:
        """添加种子失败时的降级处理"""
        logger.warning(f"添加种子降级处理: {magnet_link[:30]}...")
        # 简单重试或记录到队列
        await self._metrics.record_counter(
            "qbittorrent.torrent.add_fallback",
            1.0
        )
        return False

    async def _is_duplicate(self, torrent_hash: str) -> bool:
        """检查种子是否已存在"""
        url = f"{self._base_url}/api/v2/torrents/info"
        params = {'hashes': torrent_hash}

        # 尝试从缓存获取
        cache_key = f"qbittorrent:torrent:{torrent_hash}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    torrents = await resp.json()
                    is_duplicate = len(torrents) > 0

                    # 缓存结果（5分钟）
                    await self._cache.set(cache_key, is_duplicate, ttl=300)
                    return is_duplicate
                else:
                    logger.warning(f"检查重复失败: HTTP {resp.status}")
                    return False
        except aiohttp.ClientError as e:
            logger.warning(f"检查重复网络错误: {str(e)}")
            return False

    async def get_torrents(
        self,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取种子列表"""
        await self.ensure_authenticated()

        url = f"{self._base_url}/api/v2/torrents/info"
        params = {}
        if category:
            params['category'] = category

        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"获取种子列表失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"获取种子列表网络错误: {str(e)}") from e

    async def delete_torrent(
        self,
        torrent_hash: str,
        delete_files: bool = False
    ) -> bool:
        """删除种子"""
        await self.ensure_authenticated()

        url = f"{self._base_url}/api/v2/torrents/delete"
        data = {
            'hashes': torrent_hash,
            'deleteFiles': 'true' if delete_files else 'false'
        }

        try:
            async with self._session.post(url, data=data) as resp:
                if resp.status == 200:
                    logger.info(f"删除种子成功: {torrent_hash[:8]}")
                    await self._metrics.record_counter(
                        "qbittorrent.torrent.deleted",
                        1.0
                    )
                    return True
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"删除种子失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"删除种子网络错误: {str(e)}") from e

    async def pause_torrent(self, torrent_hash: str) -> bool:
        """暂停种子"""
        await self.ensure_authenticated()

        url = f"{self._base_url}/api/v2/torrents/pause"
        data = {'hashes': torrent_hash}

        try:
            async with self._session.post(url, data=data) as resp:
                if resp.status == 200:
                    logger.info(f"暂停种子成功: {torrent_hash[:8]}")
                    return True
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"暂停种子失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"暂停种子网络错误: {str(e)}") from e

    async def resume_torrent(self, torrent_hash: str) -> bool:
        """恢复种子"""
        await self.ensure_authenticated()

        url = f"{self._base_url}/api/v2/torrents/resume"
        data = {'hashes': torrent_hash}

        try:
            async with self._session.post(url, data=data) as resp:
                if resp.status == 200:
                    logger.info(f"恢复种子成功: {torrent_hash[:8]}")
                    return True
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"恢复种子失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"恢复种子网络错误: {str(e)}") from e

    async def get_torrent_properties(self, torrent_hash: str) -> Dict[str, Any]:
        """获取种子属性"""
        await self.ensure_authenticated()

        url = f"{self._base_url}/api/v2/torrents/properties"
        params = {'hash': torrent_hash}

        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"获取种子属性失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"获取种子属性网络错误: {str(e)}") from e

    async def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        """获取种子文件列表"""
        await self.ensure_authenticated()

        url = f"{self._base_url}/api/v2/torrents/files"
        params = {'hash': torrent_hash}

        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"获取种子文件失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"获取种子文件网络错误: {str(e)}") from e

    async def add_torrents_batch(
        self,
        torrents: List[Tuple[str, str]],
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """批量添加种子"""
        logger.info(f"开始批量添加 {len(torrents)} 个种子 (批次大小: {batch_size})")

        results = {
            'success_count': 0,
            'failed_count': 0,
            'skipped_count': 0,
            'results': []
        }

        # 使用批处理器
        for i in range(0, len(torrents), batch_size):
            batch = torrents[i:i + batch_size]

            # 并发处理当前批次
            tasks = []
            for magnet_link, category in batch:
                task = asyncio.create_task(
                    self._add_torrent_safe(magnet_link, category)
                )
                tasks.append(task)

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理批次结果
            for j, result in enumerate(batch_results):
                magnet_link, category = batch[j]

                if isinstance(result, Exception):
                    logger.error(f"添加种子失败: {magnet_link[:30]}... - {str(result)}")
                    results['failed_count'] += 1
                    results['results'].append({
                        'magnet': magnet_link,
                        'category': category,
                        'status': 'failed',
                        'error': str(result)
                    })
                elif result is True:
                    results['success_count'] += 1
                    results['results'].append({
                        'magnet': magnet_link,
                        'category': category,
                        'status': 'success'
                    })
                elif result is False:
                    results['skipped_count'] += 1
                    results['results'].append({
                        'magnet': magnet_link,
                        'category': category,
                        'status': 'skipped',
                        'reason': 'duplicate'
                    })

        logger.info(
            f"批量添加完成: 成功 {results['success_count']}, "
            f"失败 {results['failed_count']}, 跳过 {results['skipped_count']}"
        )

        return results

    async def _add_torrent_safe(self, magnet_link: str, category: str) -> bool:
        """安全添加单个种子 (用于批量操作)"""
        try:
            async with managed_resource(
                create_func=lambda: None,  # 不需要额外资源
                resource_id=f"add_torrent_{id(magnet_link)}"
            ):
                result = await self.add_torrent(magnet_link, category)
                return result
        except Exception as e:
            logger.error(f"批量添加失败: {magnet_link[:30]}... - {str(e)}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """获取客户端统计信息"""
        return {
            "resource_id": self.resource_id,
            "authenticated": self._authenticated,
            "circuit_breaker": {
                "state": self._circuit_breaker.state.value,
                "failure_count": self._circuit_breaker.failure_count,
                "success_count": self._circuit_breaker.success_count
            },
            "rate_limiter": {
                "total_requests": self._rate_limiter.stats["total_requests"],
                "allowed_requests": self._rate_limiter.stats["allowed_requests"],
                "rejected_requests": self._rate_limiter.stats["rejected_requests"]
            },
            "throttler": {
                "active_tasks": self._throttler.get_stats().active_tasks,
                "queue_size": self._throttler.get_stats().queue_size
            }
        }

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._initialize_session()
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """异步上下文管理器退出"""
        await self.close()
        return False
