"""
增强的网页爬虫 - 集成所有健壮性功能

特性：
- 集成统一异常处理和重试机制
- 使用增强的缓存系统
- 使用资源管理上下文管理器
- 使用统一熔断器和限流
- 集成监控和指标
- 智能错误恢复
- 批量操作优化
"""

import asyncio
import logging
import time
import hashlib
import random
from typing import List, Dict, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque

from crawl4ai import AsyncWebCrawler
from .exceptions_enhanced import retry, get_retry_config, RetryableError, NonRetryableError
from .enhanced_cache import get_global_cache
from .resource_manager import (
    BaseAsyncResource, AsyncResourcePool, managed_resource, get_global_tracker
)
from .concurrency import (
    AsyncThrottler, AsyncBatchProcessor, get_concurrency_config,
    async_throttle
)
from .monitoring import (
    get_metrics_collector, get_health_checker, PerformanceMonitor
)
from .circuit_breaker import (
    get_global_traffic_controller, UnifiedCircuitBreaker, UnifiedRateLimiter,
    CircuitBreakerConfig, RateLimitConfig, RateLimitStrategy
)

from .config import AppConfig
from .qbittorrent_client_enhanced import EnhancedQBittorrentClient
from .ai_classifier import AIClassifier
from .notifications import NotificationManager
from .utils import parse_magnet, validate_magnet_link
from .exceptions import CrawlerError

logger = logging.getLogger(__name__)


@dataclass
class TorrentInfo:
    """种子信息数据类"""
    title: str
    detail_url: str
    magnet_link: str = ""
    size: str = ""
    seeders: int = 0
    leechers: int = 0
    category: str = ""
    status: str = "pending"


@dataclass
class CrawlResult:
    """爬取结果"""
    url: str
    success: bool
    torrents: List[TorrentInfo]
    error: Optional[str] = None
    response_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class EnhancedWebCrawler(BaseAsyncResource):
    """
    增强的网页爬虫

    集成所有健壮性功能的企业级爬虫
    """

    def __init__(
        self,
        config: AppConfig,
        qbt_client: EnhancedQBittorrentClient
    ):
        super().__init__(f"web_crawler_{id(self)}")
        self.config = config
        self.qbt_client = qbt_client

        # 初始化增强模块
        self._init_enhanced_features()

        # 爬虫资源池
        self._crawler_pool: Optional[AsyncResourcePool] = None

        # 统计信息
        self.stats = {
            'pages_crawled': 0,
            'torrents_found': 0,
            'magnets_extracted': 0,
            'torrents_added': 0,
            'duplicates_skipped': 0,
            'errors': 0
        }

        self.processed_hashes: Set[str] = set()

    def _init_enhanced_features(self):
        """初始化增强功能"""
        # 获取全局组件
        self._cache = get_global_cache()
        self._metrics = get_metrics_collector()
        self._health_checker = get_health_checker()
        self._traffic_controller = get_global_traffic_controller()
        self._tracker = get_global_tracker()
        self._performance_monitor = PerformanceMonitor(self._metrics)

        # 初始化组件
        self.ai_classifier = AIClassifier(self.config.deepseek)
        self.notification_manager = NotificationManager(
            self.config.notifications.model_dump()
        )

        # 注册健康检查
        self._health_checker.register_check(
            f"web_crawler_{self.resource_id}",
            self._check_health,
            critical=False
        )

        # 配置熔断器
        cb_config = CircuitBreakerConfig(
            failure_threshold=getattr(
                self.config.web_crawler,
                'circuit_breaker_threshold',
                5
            ),
            success_threshold=3,
            timeout=300.0,
            name=f"crawler_{self.resource_id}"
        )
        self._circuit_breaker = self._traffic_controller.add_circuit_breaker(
            f"crawler_{self.resource_id}",
            cb_config
        )

        # 配置限流器
        rl_config = RateLimitConfig(
            rate=getattr(
                self.config.web_crawler,
                'max_requests_per_minute',
                60
            ) / 60.0,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            name=f"crawler_{self.resource_id}"
        )
        self._rate_limiter = self._traffic_controller.add_rate_limiter(
            f"crawler_{self.resource_id}",
            rl_config
        )

        # 配置节流器
        concurrency_config = get_concurrency_config("medium")
        self._throttler = AsyncThrottler(concurrency_config['max_concurrent'])

        # 配置批处理器
        self._batch_processor = AsyncBatchProcessor(
            batch_size=5,
            max_wait_time=2.0,
            max_workers=concurrency_config['max_workers']
        )

    async def _do_close(self):
        """关闭资源"""
        if self._crawler_pool:
            await self._crawler_pool.close()

        # 清理AI分类器
        if hasattr(self.ai_classifier, 'cleanup'):
            await self.ai_classifier.cleanup()

        logger.info(f"WebCrawler已关闭: {self.resource_id}")

    async def _check_health(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            if not self._crawler_pool:
                return {
                    "status": "warning",
                    "message": "Crawler pool not initialized"
                }

            pool_stats = self._crawler_pool.get_stats()
            return {
                "status": "healthy",
                "message": f"Pool size: {pool_stats['pool_size']}, "
                          f"Used: {pool_stats['used_size']}",
                "pool_stats": pool_stats
            }
        except Exception as e:
            return {
                "status": "critical",
                "message": f"Health check failed: {str(e)}"
            }

    async def _create_crawler(self) -> AsyncWebCrawler:
        """创建新的爬虫实例"""
        crawler = AsyncWebCrawler(
            headless=True,
            browser_type="chromium",
            verbose=False,
            delay_before_return_html=2.0,
            js_code=[
                "window.scrollTo(0, document.body.scrollHeight);",
                "await new Promise(resolve => setTimeout(resolve, 1000));"
            ]
        )
        await crawler.start()

        # 注册到资源跟踪器
        await self._tracker.register_resource(
            resource_id=f"crawler_instance_{id(crawler)}",
            resource_type="web_crawler",
            resource=crawler,
            size_bytes=50 * 1024 * 1024,  # 50MB估算
            metadata={
                "created_at": datetime.now().isoformat()
            }
        )

        return crawler

    async def _initialize_pool(self):
        """初始化爬虫资源池"""
        pool_size = getattr(
            self.config.web_crawler,
            'connection_pool_size',
            5
        )

        self._crawler_pool = AsyncResourcePool(
            create_func=self._create_crawler,
            max_size=pool_size,
            min_size=2,
            acquire_timeout=30.0,
            idle_timeout=300.0,
            resource_type="web_crawler"
        )

        await self._initialize_pool_base()

    async def _initialize_pool_base(self):
        """初始化资源池基础"""
        await self._crawler_pool._initialize_pool()

    async def _cleanup_crawler(self, crawler: AsyncWebCrawler):
        """清理爬虫实例"""
        if hasattr(crawler, 'close'):
            try:
                await crawler.close()
            except Exception as e:
                logger.warning(f"关闭爬虫失败: {str(e)}")

    async def _make_request_with_retry(
        self,
        url: str,
        **kwargs
    ) -> Any:
        """带重试的请求方法"""
        retry_config = get_retry_config("network")

        for attempt in range(retry_config.max_attempts):
            try:
                return await self._traffic_controller.call(
                    self._do_crawl,
                    circuit_breaker_name=f"crawler_{self.resource_id}",
                    rate_limiter_name=f"crawler_{self.resource_id}",
                    url=url,
                    **kwargs
                )
            except RetryableError as e:
                if attempt < retry_config.max_attempts - 1:
                    delay = retry_config.get_delay(attempt + 1)
                    logger.warning(
                        f"爬取失败 (尝试 {attempt + 1}/{retry_config.max_attempts}): "
                        f"{str(e)}，{delay:.2f}秒后重试"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"爬取失败，已达最大重试次数: {str(e)}")
                    raise
            except NonRetryableError as e:
                logger.error(f"不可重试的错误: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"未预期的错误: {str(e)}")
                raise

    async def _do_crawl(self, url: str, **kwargs) -> Any:
        """实际的爬取实现"""
        if not self._crawler_pool:
            await self._initialize_pool()

        # 获取缓存键
        cache_key = f"crawler:{hashlib.md5(url.encode()).hexdigest()}"

        # 尝试从缓存获取
        cached_result = await self._cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"缓存命中: {url}")
            return cached_result

        start_time = time.time()

        # 获取爬虫实例
        async with managed_resource(
            create_func=lambda: self._crawler_pool.acquire(),
            resource_id=f"crawl_{id(url)}",
            pool=self._crawler_pool
        ) as crawler:
            # 执行爬取
            result = await crawler.arun(url=url, **kwargs)

            response_time = (time.time() - start_time) * 1000

            # 记录性能指标
            await self._performance_monitor.track_request(
                endpoint="crawl",
                duration_ms=response_time,
                success=True
            )

            # 缓存结果
            await self._cache.set(
                cache_key,
                result,
                ttl=getattr(
                    self.config.web_crawler,
                    'cache_ttl_seconds',
                    3600
                )
            )

            return result

    async def crawl_xxxclub_search(
        self,
        search_url: str,
        max_pages: int = 1
    ) -> List[TorrentInfo]:
        """
        抓取XXXClub搜索页面
        """
        logger.info(f"🕷️ 开始抓取XXXClub搜索页面: {search_url}")

        torrents = []

        # 增强的爬虫配置
        crawler_config = self._get_crawler_config()

        try:
            for page in range(1, max_pages + 1):
                # 构建分页URL
                if page > 1:
                    if '?' in search_url:
                        page_url = f"{search_url}&page={page}"
                    else:
                        page_url = f"{search_url}?page={page}"
                else:
                    page_url = search_url

                logger.info(f"抓取第 {page}/{max_pages} 页: {page_url}")

                # 使用批处理器
                page_torrents = await self._batch_processor.process(
                    self._crawl_page,
                    page_url,
                    crawler_config
                )

                if page_torrents:
                    torrents.extend(page_torrents)
                    logger.info(f"第 {page} 页找到 {len(page_torrents)} 个种子")
                else:
                    logger.warning(f"第 {page} 页未找到种子")

                # 页面间隔
                if page < max_pages:
                    await asyncio.sleep(random.uniform(1, 3))

        except Exception as e:
            logger.error(f"抓取失败: {str(e)}")
            self.stats['errors'] += 1
            raise CrawlerError(f"抓取XXXClub失败: {str(e)}") from e

        # 更新统计
        self.stats['pages_crawled'] += max_pages
        self.stats['torrents_found'] += len(torrents)

        # 提取磁力链接
        extracted = await self._extract_magnets_from_torrents(torrents)
        self.stats['magnets_extracted'] += len(extracted)

        logger.info(
            f"抓取完成: 找到 {len(torrents)} 个种子，"
            f"提取 {len(extracted)} 个磁力链接"
        )

        return extracted

    def _get_crawler_config(self) -> Dict[str, Any]:
        """获取爬虫配置"""
        return {
            'verbose': False,
            'browser_type': 'chromium',
            'headless': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                         'AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/125.0.0.0 Safari/537.36',
            'headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                         'image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            },
            'page_timeout': getattr(
                self.config.web_crawler,
                'page_timeout',
                30000
            ),
            'wait_for': getattr(
                self.config.web_crawler,
                'wait_for',
                "css:.torrent-list"
            ),
            'delay_before_return_html': getattr(
                self.config.web_crawler,
                'delay_before_return',
                2.0
            ),
            'proxy': getattr(
                self.config.web_crawler,
                'proxy',
                None
            ),
            'viewport': {'width': 1920, 'height': 1080},
            'timezone_id': 'Asia/Shanghai',
            'locale': 'zh-CN',
        }

    async def _crawl_page(self, page_url: str, config: Dict[str, Any]) -> List[TorrentInfo]:
        """爬取单个页面"""
        try:
            result = await self._make_request_with_retry(page_url, **config)

            if not result.success:
                logger.warning(f"页面爬取失败: {page_url}")
                return []

            # 解析页面内容
            torrents = self._parse_torrent_list(result.html, page_url)

            # 过滤重复
            unique_torrents = []
            for torrent in torrents:
                if torrent.magnet_link:
                    torrent_hash, _ = parse_magnet(torrent.magnet_link)
                    if torrent_hash and torrent_hash not in self.processed_hashes:
                        self.processed_hashes.add(torrent_hash)
                        unique_torrents.append(torrent)

            return unique_torrents

        except Exception as e:
            logger.error(f"爬取页面失败 {page_url}: {str(e)}")
            return []

    def _parse_torrent_list(self, html: str, url: str) -> List[TorrentInfo]:
        """解析种子列表"""
        # 这里应该实现具体的解析逻辑
        # 由于需要 BeautifulSoup 或其他解析库，这里提供框架
        torrents = []

        # 示例解析逻辑
        import re

        # 查找磁力链接
        magnet_pattern = r'magnet:\?xt=urn:btih:[a-fA-F0-9]{32,40}'
        magnets = re.findall(magnet_pattern, html)

        # 查找种子信息
        # 这里需要根据具体网站结构调整
        # 暂时返回空列表，实际使用时需要完善

        return torrents

    async def _extract_magnets_from_torrents(
        self,
        torrents: List[TorrentInfo]
    ) -> List[TorrentInfo]:
        """从种子列表中提取磁力链接"""
        extracted = []

        for torrent in torrents:
            if torrent.magnet_link and validate_magnet_link(torrent.magnet_link):
                # 使用AI分类器分类
                try:
                    category = await self.ai_classifier.classify_content(
                        torrent.title
                    )
                    torrent.category = category
                except Exception as e:
                    logger.warning(f"分类失败: {str(e)}")
                    torrent.category = "未分类"

                extracted.append(torrent)

        return extracted

    async def crawl_batch(
        self,
        urls: List[str],
        max_concurrent: int = 5
    ) -> List[CrawlResult]:
        """批量爬取"""
        logger.info(f"开始批量爬取 {len(urls)} 个URL")

        results = []

        # 使用节流器控制并发
        semaphore = asyncio.Semaphore(max_concurrent)

        async def crawl_single(url: str) -> CrawlResult:
            async with semaphore:
                start_time = time.time()
                try:
                    result = await self._make_request_with_retry(url)
                    response_time = (time.time() - start_time) * 1000

                    return CrawlResult(
                        url=url,
                        success=True,
                        torrents=[],
                        response_time=response_time
                    )
                except Exception as e:
                    response_time = (time.time() - start_time) * 1000
                    return CrawlResult(
                        url=url,
                        success=False,
                        torrents=[],
                        error=str(e),
                        response_time=response_time
                    )

        # 并发执行
        tasks = [crawl_single(url) for url in urls]
        results = await asyncio.gather(*tasks)

        # 统计
        success_count = sum(1 for r in results if r.success)
        logger.info(
            f"批量爬取完成: 成功 {success_count}/{len(urls)}"
        )

        return results

    async def process_and_add_torrents(
        self,
        torrents: List[TorrentInfo]
    ) -> Dict[str, int]:
        """处理并添加种子到qBittorrent"""
        logger.info(f"开始处理 {len(torrents)} 个种子")

        results = {
            'added': 0,
            'skipped': 0,
            'failed': 0
        }

        # 按分类分组
        categories = defaultdict(list)
        for torrent in torrents:
            categories[torrent.category].append(torrent)

        # 处理每个分类
        for category, category_torrents in categories.items():
            logger.info(f"处理分类: {category} ({len(category_torrents)} 个种子)")

            # 转换为(magnet, category)格式
            magnet_pairs = [
                (torrent.magnet_link, category)
                for torrent in category_torrents
            ]

            try:
                # 使用批量添加
                batch_result = await self.qbt_client.add_torrents_batch(
                    magnet_pairs,
                    batch_size=10
                )

                results['added'] += batch_result['success_count']
                results['skipped'] += batch_result['skipped_count']
                results['failed'] += batch_result['failed_count']

            except Exception as e:
                logger.error(f"批量添加失败: {str(e)}")
                results['failed'] += len(category_torrents)

        # 更新统计
        self.stats['torrents_added'] += results['added']
        self.stats['duplicates_skipped'] += results['skipped']

        logger.info(
            f"处理完成: 添加 {results['added']}, "
            f"跳过 {results['skipped']}, 失败 {results['failed']}"
        )

        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        circuit_stats = self._circuit_breaker.get_stats()
        rate_limiter_stats = self._rate_limiter.get_stats()

        return {
            "resource_id": self.resource_id,
            "stats": self.stats.copy(),
            "circuit_breaker": circuit_stats,
            "rate_limiter": rate_limiter_stats,
            "throttler": {
                "active_tasks": self._throttler.get_stats().active_tasks,
                "queue_size": self._throttler.get_stats().queue_size
            },
            "processed_hashes": len(self.processed_hashes)
        }

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._initialize_pool()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """异步上下文管理器退出"""
        await self.close()
        return False
