"""
WebCrawler核心模块

整合所有子模块，提供完整的Web爬虫功能。

主要组件:
- WebCrawler: 主爬虫类
- CrawlerContext: 爬虫上下文
- CrawlResult: 爬取结果
"""

from typing import Dict, List, Optional, Any, Union
import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

from .models import SiteConfig, MemoryMonitor
from .cache import CacheManager
from .resilience import ResilienceManager
from .stats import StatsCollector
from .adapters import AdaptiveParser, AdapterFactory, SiteType
from .optimizer import OptimizedAsyncWebCrawler, OptimizationLevel

logger = logging.getLogger(__name__)


class CrawlStatus(Enum):
    """爬取状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRY = "retry"


class ContentType(Enum):
    """内容类型"""
    HTML = "html"
    JSON = "json"
    XML = "xml"
    TEXT = "text"
    BINARY = "binary"


@dataclass
class CrawlRequest:
    """爬取请求"""
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    data: Optional[Dict[str, Any]] = None
    timeout: float = 30.0
    retry_count: int = 0
    max_retries: int = 3
    callback: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CrawlResult:
    """爬取结果"""
    url: str
    status: CrawlStatus
    status_code: Optional[int] = None
    content: Optional[str] = None
    content_type: Optional[ContentType] = None
    response_time: float = 0.0
    error_message: Optional[str] = None
    retry_count: int = 0
    cached: bool = False
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'url': self.url,
            'status': self.status.value,
            'status_code': self.status_code,
            'content_length': len(self.content) if self.content else 0,
            'content_type': self.content_type.value if self.content_type else None,
            'response_time': self.response_time,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'cached': self.cached,
            'metadata': self.metadata,
        }


@dataclass
class CrawlerStats:
    """爬虫统计"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cached_requests: int = 0
    retried_requests: int = 0
    total_response_time: float = 0.0
    average_response_time: float = 0.0
    total_bytes: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def average_throughput(self) -> float:
        """平均吞吐量 (bytes/second)"""
        if self.end_time == 0 or self.start_time == 0:
            return 0.0
        duration = self.end_time - self.start_time
        if duration <= 0:
            return 0.0
        return self.total_bytes / duration


class WebCrawler:
    """Web爬虫主类

    整合缓存、弹性设计、统计、适配器和性能优化的完整爬虫解决方案
    """

    def __init__(
        self,
        config: Any,  # AppConfig
        qbt_client: Any,  # QBittorrentClient
        site_configs: Optional[List[SiteConfig]] = None,
        optimization_level: OptimizationLevel = OptimizationLevel.MODERATE
    ):
        """
        初始化WebCrawler

        Args:
            config: 应用程序配置
            qbt_client: qBittorrent客户端
            site_configs: 网站配置列表
            optimization_level: 优化级别
        """
        self.config = config
        self.qbt_client = qbt_client
        self.site_configs = site_configs or []

        # 子组件
        self.memory_monitor = MemoryMonitor(
            memory_limit_mb=getattr(config, 'memory_limit_mb', 100)
        )

        self.cache_manager = CacheManager(
            max_size=getattr(config, 'cache_size', 1000),
            ttl=getattr(config, 'cache_ttl', 3600)
        )

        self.resilience_manager = ResilienceManager(
            max_retries=getattr(config, 'max_retries', 3),
            timeout=getattr(config, 'timeout', 30.0)
        )

        self.stats_collector = StatsCollector()

        # 适配器
        self.parser = AdaptiveParser(self.site_configs) if self.site_configs else None

        # 性能优化器
        self.optimizer = OptimizedAsyncWebCrawler(
            config=self.site_configs[0] if self.site_configs else SiteConfig(
                name="default",
                url_pattern="*",
                selectors={}
            ),
            memory_monitor=self.memory_monitor,
            optimization_level=optimization_level
        )

        # 状态
        self._running = False
        self._stats = CrawlerStats()

        # 设置回调
        self.optimizer.on_success = self._on_crawl_success
        self.optimizer.on_error = self._on_crawl_error

    async def start(self):
        """启动爬虫"""
        logger.info("Starting WebCrawler...")
        await self.optimizer.start()
        self._running = True
        self._stats.start_time = asyncio.get_event_loop().time()
        logger.info("WebCrawler started successfully")

    async def stop(self):
        """停止爬虫"""
        logger.info("Stopping WebCrawler...")
        self._running = False
        self._stats.end_time = asyncio.get_event_loop().time()
        await self.optimizer.stop()
        logger.info("WebCrawler stopped")

    async def crawl(
        self,
        urls: Union[str, List[str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        爬取URL

        Args:
            urls: 单个URL或URL列表
            **kwargs: 额外参数

        Returns:
            Dict[str, Any]: 爬取结果
        """
        if isinstance(urls, str):
            urls = [urls]

        logger.info(f"Starting to crawl {len(urls)} URLs")

        # 创建请求列表
        requests = [
            CrawlRequest(url=url, **kwargs)
            for url in urls
        ]

        # 执行爬取
        results = await self._crawl_batch(requests)

        # 统计结果
        self._update_stats(results)

        # 生成摘要
        summary = self._generate_summary(results)

        logger.info(
            f"Crawl completed. Success: {summary['successful']}, "
            f"Failed: {summary['failed']}, "
            f"Cached: {summary['cached']}"
        )

        return {
            'summary': summary,
            'results': [result.to_dict() for result in results],
            'stats': self.get_stats(),
        }

    async def _crawl_batch(self, requests: List[CrawlRequest]) -> List[CrawlResult]:
        """
        批量爬取

        Args:
            requests: 请求列表

        Returns:
            List[CrawlResult]: 结果列表
        """
        results = []

        # 创建信号量限制并发
        max_concurrent = getattr(self.config, 'max_concurrent', 10)
        semaphore = asyncio.Semaphore(max_concurrent)

        # 创建任务
        tasks = [
            self._crawl_single(request, semaphore)
            for request in requests
        ]

        # 并发执行
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                results.append(result)
            except Exception as e:
                logger.error(f"Crawl task error: {e}")
                results.append(CrawlResult(
                    url="unknown",
                    status=CrawlStatus.FAILED,
                    error_message=str(e)
                ))

        return results

    async def _crawl_single(
        self,
        request: CrawlRequest,
        semaphore: asyncio.Semaphore
    ) -> CrawlResult:
        """
        爬取单个请求

        Args:
            request: 爬取请求
            semaphore: 信号量

        Returns:
            CrawlResult: 爬取结果
        """
        start_time = asyncio.get_event_loop().time()

        # 检查缓存
        cache_key = self._generate_cache_key(request)
        cached_result = await self.cache_manager.get(cache_key)

        if cached_result is not None:
            self._stats.cached_requests += 1
            return CrawlResult(
                url=request.url,
                status=CrawlStatus.SUCCESS,
                content=cached_result,
                response_time=0.0,
                cached=True
            )

        # 使用弹性设计进行爬取
        async with semaphore:
            result = await self.resilience_manager.execute(
                self._execute_crawl,
                request
            )

            # 缓存结果
            if result.status == CrawlStatus.SUCCESS and result.content:
                await self.cache_manager.set(
                    cache_key,
                    result.content,
                    ttl=getattr(self.config, 'cache_ttl', 3600)
                )

            # 记录统计
            response_time = asyncio.get_event_loop().time() - start_time
            await self.stats_collector.record_request(
                request.url,
                response_time,
                result.status == CrawlStatus.SUCCESS
            )

            return result

    async def _execute_crawl(self, request: CrawlRequest) -> CrawlResult:
        """
        执行实际爬取

        Args:
            request: 爬取请求

        Returns:
            CrawlResult: 爬取结果
        """
        try:
            # 检查URL是否可访问
            if not self._should_crawl(request.url):
                return CrawlResult(
                    url=request.url,
                    status=CrawlStatus.SKIPPED,
                    error_message="URL filtered or blocked"
                )

            # 使用适配器解析
            if self.parser:
                # 获取合适的适配器
                adapter = self.parser.get_adapter_for_url(request.url)

                if adapter:
                    # 使用适配器解析 (简化实现)
                    content = await self._fetch_content(request.url)
                    parsed = adapter.parse(request.url, content)

                    if parsed:
                        return CrawlResult(
                            url=request.url,
                            status=CrawlStatus.SUCCESS,
                            content=json.dumps(parsed),
                            content_type=ContentType.JSON
                        )

            # 默认爬取
            content = await self._fetch_content(request.url)

            return CrawlResult(
                url=request.url,
                status=CrawlStatus.SUCCESS,
                content=content,
                content_type=ContentType.HTML
            )

        except asyncio.TimeoutError as e:
            return CrawlResult(
                url=request.url,
                status=CrawlStatus.FAILED,
                error_message=f"Timeout: {str(e)}"
            )
        except Exception as e:
            return CrawlResult(
                url=request.url,
                status=CrawlStatus.FAILED,
                error_message=str(e)
            )

    async def _fetch_content(self, url: str) -> str:
        """
        获取内容 (简化实现)

        Args:
            url: 目标URL

        Returns:
            str: 网页内容
        """
        # 这里应该是实际的HTTP请求实现
        # 简化实现：模拟网络请求
        await asyncio.sleep(0.1)
        return f"<html><title>Content from {url}</title></html>"

    def _should_crawl(self, url: str) -> bool:
        """
        检查是否应该爬取

        Args:
            url: 目标URL

        Returns:
            bool: 是否应该爬取
        """
        # 基本过滤逻辑
        blocked_extensions = ['.jpg', '.png', '.gif', '.css', '.js']
        if any(url.lower().endswith(ext) for ext in blocked_extensions):
            return False

        # 检查黑名单
        blocked_hosts = getattr(self.config, 'blocked_hosts', [])
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc
            if host in blocked_hosts:
                return False
        except Exception:
            pass

        return True

    def _generate_cache_key(self, request: CrawlRequest) -> str:
        """
        生成缓存键

        Args:
            request: 爬取请求

        Returns:
            str: 缓存键
        """
        import hashlib
        key_data = f"{request.url}:{request.method}:{json.dumps(request.data or {}, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _update_stats(self, results: List[CrawlResult]):
        """
        更新统计

        Args:
            results: 爬取结果列表
        """
        for result in results:
            self._stats.total_requests += 1

            if result.status == CrawlStatus.SUCCESS:
                self._stats.successful_requests += 1
                if result.content:
                    self._stats.total_bytes += len(result.content)
            elif result.status == CrawlStatus.FAILED:
                self._stats.failed_requests += 1

            if result.cached:
                self._stats.cached_requests += 1

            if result.retry_count > 0:
                self._stats.retried_requests += 1

            self._stats.total_response_time += result.response_time

        # 计算平均值
        if self._stats.total_requests > 0:
            self._stats.average_response_time = (
                self._stats.total_response_time / self._stats.total_requests
            )

    def _generate_summary(self, results: List[CrawlResult]) -> Dict[str, int]:
        """
        生成摘要

        Args:
            results: 爬取结果列表

        Returns:
            Dict[str, int]: 摘要统计
        """
        summary = {
            'total': len(results),
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'cached': 0,
        }

        for result in results:
            if result.status == CrawlStatus.SUCCESS:
                summary['successful'] += 1
            elif result.status == CrawlStatus.FAILED:
                summary['failed'] += 1
            elif result.status == CrawlStatus.SKIPPED:
                summary['skipped'] += 1

            if result.cached:
                summary['cached'] += 1

        return summary

    async def _on_crawl_success(self, result: Dict[str, Any]):
        """
        爬取成功回调

        Args:
            result: 爬取结果
        """
        logger.debug(f"Crawl success: {result.get('url')}")

        # 这里可以添加自定义成功处理逻辑
        # 例如：保存结果、触发后续处理等

    async def _on_crawl_error(self, result: Dict[str, Any]):
        """
        爬取错误回调

        Args:
            result: 爬取结果
        """
        logger.warning(f"Crawl error: {result.get('url')} - {result.get('error')}")

        # 这里可以添加自定义错误处理逻辑
        # 例如：记录错误、触发告警等

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            'crawler_stats': {
                'total_requests': self._stats.total_requests,
                'successful_requests': self._stats.successful_requests,
                'failed_requests': self._stats.failed_requests,
                'cached_requests': self._stats.cached_requests,
                'retried_requests': self._stats.retried_requests,
                'success_rate': self._stats.success_rate,
                'average_response_time': self._stats.average_response_time,
                'average_throughput': self._stats.average_throughput,
            },
            'optimizer_stats': self.optimizer.get_performance_stats(),
            'cache_stats': self.cache_manager.get_stats(),
            'resilience_stats': self.resilience_manager.get_stats(),
        }

    def reset_stats(self):
        """重置统计"""
        self._stats = CrawlerStats()
        self.stats_collector.reset()
        self.cache_manager.reset_stats()

    async def crawl_magnets(self, urls: List[str]) -> List[str]:
        """
        专门爬取磁力链接

        Args:
            urls: URL列表

        Returns:
            List[str]: 磁力链接列表
        """
        results = await self.crawl(urls)

        magnets = []
        for result in results['results']:
            if result['status'] == 'success' and result.get('content'):
                # 尝试从内容中提取磁力链接
                import re
                content = result['content']
                found_magnets = re.findall(r'magnet:\?[^"\'\s<>\]]+', content)
                magnets.extend(found_magnets)

        # 去重并返回
        return list(set(magnets))


# 导出
__all__ = [
    'WebCrawler',
    'CrawlRequest',
    'CrawlResult',
    'CrawlStatus',
    'ContentType',
    'CrawlerStats',
]
