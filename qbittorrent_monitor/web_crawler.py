"""
基于 crawl4ai 的网页爬虫模块

使用专业的 crawl4ai 库进行网站抓取和内容提取
"""

import asyncio
import logging
import random
import re
import urllib.parse
import time
import hashlib
from collections import defaultdict, deque
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from crawl4ai import AsyncWebCrawler, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy, CosineStrategy

from .config import AppConfig
from .qbittorrent_client import QBittorrentClient
from .ai_classifier import AIClassifier
from .notifications import NotificationManager
from .utils import parse_magnet, validate_magnet_link
from .exceptions import CrawlerError
from .resilience import RateLimiter, CircuitBreaker, LRUCache, MetricsTracker


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
    status: str = "pending"  # pending, extracted, added, failed, duplicate
    
@dataclass
class CrawlerStats:
    """爬虫性能统计"""
    requests_made: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: int = 0
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    circuit_breaker_trips: int = 0
    rate_limit_hits: int = 0
    
    def get_avg_response_time(self) -> float:
        """获取平均响应时间"""
        return sum(self.response_times) / len(self.response_times) if self.response_times else 0.0
    
    def get_cache_hit_rate(self) -> float:
        """获取缓存命中率"""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


class CrawlerResourcePool:
    def __init__(self, max_size: int, config: AppConfig, logger: logging.Logger):
        self.max_size = max_size
        self.config = config
        self.logger = logger
        self._pool: List[AsyncWebCrawler] = []
        self._semaphore = asyncio.Semaphore(max_size)

    async def acquire(self) -> AsyncWebCrawler:
        async with self._semaphore:
            if self._pool:
                return self._pool.pop()
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
            return crawler

    async def release(self, crawler: AsyncWebCrawler):
        if len(self._pool) < self.max_size:
            self._pool.append(crawler)
        else:
            await crawler.close()

    async def close_all(self):
        while self._pool:
            crawler = self._pool.pop()
            try:
                await crawler.close()
            except Exception as exc:
                self.logger.warning(f"关闭爬虫实例时出错: {exc}")


class WebCrawler:
    """基于 crawl4ai 的网页爬虫类"""
    
    def __init__(self, config: AppConfig, qbt_client: QBittorrentClient):
        self.config = config
        self.qbt_client = qbt_client
        self.logger = logging.getLogger('WebCrawler')
        
        # 初始化组件
        self.ai_classifier = AIClassifier(config.deepseek)
        self.notification_manager = NotificationManager(config.notifications.model_dump())
        
        # 连接池配置
        self._connection_pool_size = getattr(config.web_crawler, 'connection_pool_size', 5)
        self._resource_pool = CrawlerResourcePool(self._connection_pool_size, config, self.logger)
        
        # 缓存系统
        cache_size = getattr(config.web_crawler, 'cache_max_size', 1000)
        cache_ttl = getattr(config.web_crawler, 'cache_ttl_seconds', 3600)
        self._cache = LRUCache(max_size=cache_size, ttl_seconds=cache_ttl)
        
        # 性能监控
        self._performance_stats = CrawlerStats()
        self._metrics = MetricsTracker()
        
        # 断路器配置
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=getattr(config.web_crawler, 'circuit_breaker_threshold', 5),
            recovery_timeout=getattr(config.web_crawler, 'circuit_breaker_recovery_seconds', 300),
            on_state_change=self._on_circuit_state_change,
        )
        
        # 速率限制
        self._rate_limit_requests = getattr(config.web_crawler, 'max_requests_per_minute', 60)
        self._rate_limiter = RateLimiter(self._rate_limit_requests)
        
        # 线程池执行器
        self._thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # 清理状态标志
        self._is_cleaned_up = False
        self._cleanup_lock = asyncio.Lock()
        
        # 统计信息（保持向后兼容）
        self.stats = {
            'pages_crawled': 0,
            'torrents_found': 0,
            'magnets_extracted': 0,
            'torrents_added': 0,
            'duplicates_skipped': 0,
            'errors': 0
        }
        
        self.processed_hashes: Set[str] = set()
    
    async def _get_crawler_from_pool(self) -> AsyncWebCrawler:
        return await self._resource_pool.acquire()
    
    async def _return_crawler_to_pool(self, crawler: AsyncWebCrawler):
        await self._resource_pool.release(crawler)
    
    def _get_cache_key(self, url: str, **kwargs) -> str:
        """生成缓存键"""
        key_data = f"{url}:{str(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._performance_stats.cache_hits += 1
            return cached
        self._performance_stats.cache_misses += 1
        return None
    
    def _put_to_cache(self, cache_key: str, data: Any):
        self._cache.set(cache_key, data)
    
    def _check_rate_limit(self) -> bool:
        """检查是否超过速率限制"""
        allowed = self._rate_limiter.allow()
        if not allowed:
            self._performance_stats.rate_limit_hits += 1
        return allowed
    
    def _on_circuit_state_change(self, state: str):
        if state == 'open':
            self._performance_stats.circuit_breaker_trips += 1
            self.logger.warning("Crawler circuit breaker opened")
        elif state == 'half_open':
            self.logger.info("Crawler circuit breaker half-open")
        elif state == 'closed':
            self.logger.info("Crawler circuit breaker closed")
    
    def _check_circuit_breaker(self) -> bool:
        """检查断路器状态"""
        return self._circuit_breaker.allow()
    
    def _record_success(self):
        """记录成功请求"""
        self._circuit_breaker.record_success()
    
    def _record_failure(self):
        """记录失败请求"""
        self._circuit_breaker.record_failure()
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        return {
            'requests_made': self._performance_stats.requests_made,
            'cache_hits': self._performance_stats.cache_hits,
            'cache_misses': self._performance_stats.cache_misses,
            'cache_hit_rate': self._performance_stats.get_cache_hit_rate(),
            'avg_response_time': self._performance_stats.get_avg_response_time(),
            'errors': self._performance_stats.errors,
            'circuit_breaker_trips': self._performance_stats.circuit_breaker_trips,
            'circuit_breaker_state': self._circuit_breaker.state,
            'rate_limit_hits': self._performance_stats.rate_limit_hits,
            'cache_size': len(self._cache),
            'pool_size': self._connection_pool_size
        }
    
    async def cleanup(self):
        """清理所有资源"""
        async with self._cleanup_lock:
            if self._is_cleaned_up:
                return
            
            self.logger.info("开始清理WebCrawler资源...")
            
            try:
                # 关闭连接池中的所有爬虫
                await self._resource_pool.close_all()
                self.logger.debug("爬虫连接池已清理")
                
                # 清理缓存
                if hasattr(self, '_cache'):
                    self._cache.clear()
                    self.logger.debug("缓存已清理")
                
                # 关闭线程池执行器
                if hasattr(self, '_thread_pool') and self._thread_pool:
                    self._thread_pool.shutdown(wait=True)
                    self.logger.debug("线程池已关闭")
                
                # 清理AI分类器
                if hasattr(self, 'ai_classifier') and hasattr(self.ai_classifier, 'cleanup'):
                    await self.ai_classifier.cleanup()
                    self.logger.debug("AI分类器已清理")
                
                self._is_cleaned_up = True
                self.logger.info("WebCrawler资源清理完成")
                
            except Exception as e:
                self.logger.error(f"清理WebCrawler资源时出错: {str(e)}")
    
    def __del__(self):
        """析构函数，确保资源被清理"""
        if not self._is_cleaned_up:
            try:
                # 同步清理关键资源
                if hasattr(self, '_cache'):
                    self._cache.clear()
                    
                if hasattr(self, '_thread_pool') and self._thread_pool:
                    self._thread_pool.shutdown(wait=False)
                    
                # 资源在 cleanup 中已处理
                
            except Exception:
                pass  # 忽略析构时的异常
    
    async def _make_request_with_cache(self, url: str, **kwargs) -> Optional[Any]:
        """带缓存的HTTP请求方法"""
        # 检查速率限制
        if not self._check_rate_limit():
            await asyncio.sleep(1)  # 等待1秒后重试
            if not self._check_rate_limit():
                raise CrawlerError(f"Rate limit exceeded for {url}")
        
        # 检查断路器
        if not self._check_circuit_breaker():
            raise CrawlerError(f"Circuit breaker is open for {url}")
        
        # 生成缓存键
        cache_key = self._get_cache_key(url, **kwargs)
        
        # 尝试从缓存获取
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        start_time = time.time()
        crawler = None
        
        try:
            self._metrics.inc('requests')
            self._metrics.update_last_request_time(datetime.now().isoformat())
            # 从连接池获取爬虫
            crawler = await self._get_crawler_from_pool()
            
            # 执行请求
            result = await crawler.arun(
                url=url,
                **kwargs
            )
            
            # 记录性能指标
            response_time = time.time() - start_time
            self._performance_stats.requests_made += 1
            self._performance_stats.response_times.append(response_time)
            self._metrics.record_response(response_time)
            
            # 记录成功
            self._record_success()
            
            # 缓存结果
            self._put_to_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            # 记录失败
            self._record_failure()
            self._performance_stats.errors += 1
            self._metrics.inc('errors')
            
            self.logger.error(f"Request failed for {url}: {str(e)}")
            raise CrawlerError(f"Failed to crawl {url}: {str(e)}") from e
            
        finally:
            # 返回爬虫到连接池
            if crawler:
                await self._return_crawler_to_pool(crawler)
     
    async def crawl_xxxclub_search(self, search_url: str, max_pages: int = 1) -> List[TorrentInfo]:
        """
        抓取XXXClub搜索页面
        
        Args:
            search_url: 搜索页面URL
            max_pages: 最大抓取页数
            
        Returns:
            种子信息列表
        """
        self.logger.info(f"🕷️ 开始抓取XXXClub搜索页面: {search_url}")
        torrents = []
        
        # 增强的爬虫配置，模拟真实用户行为，使用配置文件参数
        crawler_config = {
            'verbose': False,
            'browser_type': 'chromium',
            'headless': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'Referer': 'https://www.google.com/',
            },
            'page_timeout': self.config.web_crawler.page_timeout,
            'wait_for': self.config.web_crawler.wait_for,
            'delay_before_return_html': self.config.web_crawler.delay_before_return,
            'proxy': self.config.web_crawler.proxy,
            'viewport': {'width': 1920, 'height': 1080},
            'timezone_id': 'Asia/Shanghai',
            'locale': 'zh-CN',
            'geolocation': {'latitude': 39.9042, 'longitude': 116.4074},  # 北京坐标
            'permissions': ['geolocation'],
            'extra_http_headers': {
                'DNT': '1',
                'Sec-Ch-Ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
            }
        }
        
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
                    
                    self.logger.info(f"📄 抓取第 {page} 页: {page_url}")
                    
                    # 智能重试机制，使用配置参数
                    max_retries = self.config.web_crawler.max_retries
                    base_delay = self.config.web_crawler.base_delay
                    success = False
                    last_error = None

                    for attempt in range(max_retries):
                        try:
                            if attempt > 0:
                                # 指数退避 + 随机抖动，限制最大延迟
                                delay = min(base_delay * (2 ** (attempt - 1)) + random.uniform(0, 3),
                                          self.config.web_crawler.max_delay)
                                self.logger.info(f"🔄 第 {page} 页重试 {attempt+1}/{max_retries}, 等待 {delay:.1f} 秒")
                                await asyncio.sleep(delay)

                            # 动态调整爬虫参数
                            current_config = crawler_config.copy()
                            if attempt > 1:  # 第二次重试后增加等待时间
                                current_config['wait_for'] = min(current_config['wait_for'] * 2, 15)
                                current_config['delay_before_return_html'] = min(current_config['delay_before_return_html'] * 2, 8)
                            
                            # 使用缓存请求方法抓取页面
                            result = await self._make_request_with_cache(
                                url=page_url,
                                wait_for=current_config['wait_for'],
                                js_code=None if attempt < 2 else "window.scrollTo(0, document.body.scrollHeight);",  # 第三次重试后模拟滚动
                                css_selector="ul.tsearch li",
                                bypass_cache=True,
                                page_timeout=current_config['page_timeout'],
                                delay_before_return_html=current_config['delay_before_return_html'],
                                extra_http_headers={
                                    'X-Requested-With': 'XMLHttpRequest' if attempt > 1 else None
                                }
                            )
                            
                            if result.success:
                                success = True
                                break  # 成功，跳出重试循环
                            else:
                                error_msg = str(result.error_message) if result.error_message else "Unknown error"
                                if "ERR_CONNECTION_RESET" in error_msg or "Connection reset" in error_msg:
                                    self.logger.warning(f"⚠️ 第 {page} 页连接被重置，尝试 {attempt+1}/{max_retries}")
                                    if attempt < max_retries - 1:
                                        continue  # 继续重试
                                else:
                                    self.logger.warning(f"⚠️ 第 {page} 页抓取失败: {error_msg}")
                                    if attempt < max_retries - 1:
                                        continue  # 继续重试
                                break  # 非重试类错误，直接跳出
                                
                        except Exception as e:
                            error_msg = str(e)
                            if "ERR_CONNECTION_RESET" in error_msg or "Connection reset" in error_msg:
                                self.logger.warning(f"⚠️ 第 {page} 页连接重置异常，尝试 {attempt+1}/{max_retries}")
                                if attempt < max_retries - 1:
                                    continue  # 继续重试
                            else:
                                self.logger.error(f"❌ 第 {page} 页抓取异常: {error_msg}")
                                if attempt < max_retries - 1:
                                    continue  # 继续重试
                            break  # 最后一次尝试或非重试类错误
                    
                    # 检查是否成功抓取
                    if not success:
                        self.logger.error(f"❌ 第 {page} 页经过 {max_retries} 次重试后仍然失败")
                        
                        # 如果是第一页就失败，提供用户指导
                        if page == 1:
                            self.logger.warning("🚨 搜索页面抓取被阻止，可能遇到反爬虫机制")
                            self.logger.info("💡 建议解决方案:")
                            self.logger.info("   1. 手动访问搜索页面，查看是否需要验证码")
                            self.logger.info("   2. 逐个复制种子详情页面的磁力链接到剪贴板")
                            self.logger.info("   3. 程序会自动检测并添加单个磁力链接")
                            self.logger.info(f"   4. 搜索页面: {page_url}")
                            
                            # 早期退出，避免浪费更多时间
                            break
                        continue  # 继续尝试下一页
                    
                    # 解析页面内容
                    try:
                        page_torrents = await self._parse_xxxclub_content(result, search_url)
                        torrents.extend(page_torrents)
                        
                        self.stats['pages_crawled'] += 1
                        self.logger.info(f"✅ 第 {page} 页解析完成，找到 {len(page_torrents)} 个种子")
                        
                        # 如果没有找到种子，可能已经到最后一页
                        if not page_torrents:
                            self.logger.info("📄 没有找到更多种子，停止分页抓取")
                            break
                    except Exception as e:
                        self.logger.error(f"❌ 第 {page} 页解析失败: {str(e)}")
                        continue
                    
                    # 添加延迟避免请求过快
                    if page < max_pages:  # 不是最后一页
                        await asyncio.sleep(3 + (page % 3))  # 3-5秒随机延迟
            
            self.stats['torrents_found'] = len(torrents)
            
            if torrents:
                self.logger.info(f"🎯 搜索页面抓取完成，总共找到 {len(torrents)} 个种子")
            else:
                self.logger.warning("⚠️ 未找到任何种子")
                self.logger.info("💡 可能的原因:")
                self.logger.info("   - 搜索关键词无结果")
                self.logger.info("   - 网站反爬虫机制阻止访问")
                self.logger.info("   - 网页结构可能发生变化")
                self.logger.info("💡 建议:")
                self.logger.info("   - 手动访问页面确认内容")
                self.logger.info("   - 尝试复制单个磁力链接")
            
            return torrents
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"❌ 抓取搜索页面失败: {str(e)}")
            
            # 提供详细的错误指导
            if "ERR_CONNECTION_RESET" in str(e):
                self.logger.info("🚨 连接被重置错误通常表示:")
                self.logger.info("   - 网站检测到自动化访问")
                self.logger.info("   - IP可能被临时限制")
                self.logger.info("   - 需要使用VPN或代理")
            
            self.logger.info("💡 替代方案:")
            self.logger.info("   1. 手动访问XXXClub搜索页面")
            self.logger.info("   2. 复制单个磁力链接到剪贴板")
            self.logger.info("   3. 程序会自动检测并添加")
            
            raise CrawlerError(f"抓取搜索页面失败: {str(e)}") from e
    
    async def _parse_xxxclub_content(self, crawl_result, base_url: str) -> List[TorrentInfo]:
        """解析 crawl4ai 抓取的内容"""
        torrents = []
        
        try:
            # 暂时跳过LLM提取，直接使用简单解析方法
            # TODO: 后续重新实现LLM提取功能
            self.logger.info("📝 使用BeautifulSoup解析网页内容")
            return await self._simple_parse_xxxclub(crawl_result.cleaned_html, base_url)
            
        except Exception as e:
            self.logger.error(f"❌ 解析内容失败，使用简单解析: {str(e)}")
            return await self._simple_parse_xxxclub(crawl_result.cleaned_html, base_url)
    
    async def _simple_parse_xxxclub(self, html_content: str, base_url: str) -> List[TorrentInfo]:
        """简单的正则表达式解析方法"""
        torrents = []
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 查找所有li元素（除了第一个标题行）
            list_items = soup.find_all('li')
            
            # 跳过第一个li（标题行）
            if len(list_items) > 1:
                list_items = list_items[1:]
            
            self.logger.info(f"📊 找到 {len(list_items)} 个种子项")
            
            for item in list_items:
                try:
                    # 查找所有span元素
                    spans = item.find_all('span')
                    if len(spans) < 6:  # 至少需要6个span
                        continue
                    
                    # 第二个span包含种子详情链接
                    name_span = spans[1]
                    detail_link_elem = name_span.find('a', href=lambda x: x and '/torrents/details/' in x)
                    if not detail_link_elem:
                        continue
                    
                    detail_link = detail_link_elem['href']
                    title = detail_link_elem.get_text(strip=True)
                    
                    if not title:
                        continue
                    
                    # 构建完整URL
                    if detail_link.startswith('/'):
                        parsed_base = urllib.parse.urlparse(base_url)
                        detail_url = f"{parsed_base.scheme}://{parsed_base.netloc}{detail_link}"
                    else:
                        detail_url = detail_link
                    
                    # 提取其他信息
                    # 第四个span包含大小
                    size = spans[3].get_text(strip=True) if len(spans) > 3 else ""
                    
                    # 第五个和第六个span包含seeders和leechers  
                    seeders = 0
                    if len(spans) > 4 and spans[4].get_text(strip=True).isdigit():
                        seeders = int(spans[4].get_text(strip=True))
                    
                    leechers = 0
                    if len(spans) > 5 and spans[5].get_text(strip=True).isdigit():
                        leechers = int(spans[5].get_text(strip=True))
                    
                    torrent_info = TorrentInfo(
                        title=title,
                        detail_url=detail_url,
                        size=size,
                        seeders=seeders,
                        leechers=leechers
                    )
                    
                    torrents.append(torrent_info)
                    self.logger.debug(f"✅ 解析种子: {title[:50]}... | 大小: {size} | S/L: {seeders}/{leechers}")
                    
                except Exception as e:
                    self.logger.debug(f"解析种子项失败: {str(e)}")
                    continue
            
            return torrents
            
        except Exception as e:
            self.logger.error(f"❌ 简单解析失败: {str(e)}")
            return []
    
    async def extract_magnet_links(self, torrents: List[TorrentInfo]) -> List[TorrentInfo]:
        """从种子详情页面提取磁力链接"""
        self.logger.info(f"🔗 开始提取 {len(torrents)} 个种子的磁力链接")

        # 如果启用并发且种子数量较多，使用并发提取
        if (self.config.web_crawler.max_concurrent_extractions > 1 and
            len(torrents) > self.config.web_crawler.max_concurrent_extractions):
            return await self._extract_magnet_links_concurrent(torrents)
        else:
            return await self._extract_magnet_links_sequential(torrents)

    async def _extract_magnet_links_concurrent(self, torrents: List[TorrentInfo]) -> List[TorrentInfo]:
        """并发提取磁力链接"""
        self.logger.info(f"🚀 使用并发模式提取磁力链接，最大并发数: {self.config.web_crawler.max_concurrent_extractions}")

        # 分批处理
        batch_size = self.config.web_crawler.max_concurrent_extractions
        results = []

        for i in range(0, len(torrents), batch_size):
            batch = torrents[i:i + batch_size]
            self.logger.info(f"📦 处理批次 {i//batch_size + 1}/{(len(torrents) + batch_size - 1)//batch_size}: {len(batch)} 个种子")

            # 并发处理当前批次
            tasks = []
            for torrent in batch:
                task = asyncio.create_task(self._extract_single_magnet_link(torrent))
                tasks.append(task)

            # 等待当前批次完成
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    self.logger.error(f"❌ 提取失败: {batch[j].title[:50]}... - {str(result)}")
                    batch[j].status = "failed"
                    self.stats['errors'] += 1
                else:
                    batch[j] = result

            results.extend(batch)

            # 批次间延迟
            if i + batch_size < len(torrents):
                delay = self.config.web_crawler.inter_request_delay * 2  # 批次间延迟稍长
                await asyncio.sleep(delay)

        successful_extractions = len([t for t in results if t.status == "extracted"])
        self.logger.info(f"🎯 并发磁力链接提取完成: {successful_extractions}/{len(results)} 成功")

        return results

    async def _extract_single_magnet_link(self, torrent: TorrentInfo) -> TorrentInfo:
        """提取单个种子的磁力链接"""
        # 增强型详情页爬虫配置，使用配置参数
        crawler_config = {
            'verbose': False,
            'browser_type': 'chromium',
            'headless': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://www.google.com/',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            },
            'page_timeout': self.config.web_crawler.page_timeout,
            'wait_for': self.config.web_crawler.wait_for,
            'delay_before_return_html': self.config.web_crawler.delay_before_return,
            'proxy': self.config.web_crawler.proxy,
            'viewport': {'width': 1920, 'height': 1080},
            'timezone_id': 'Asia/Shanghai',
            'locale': 'zh-CN',
            'extra_http_headers': {
                'DNT': '1',
                'Sec-Ch-Ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
            }
        }

        max_retries = self.config.web_crawler.max_retries
        base_delay = self.config.web_crawler.base_delay

        for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        # 指数退避 + 随机抖动，限制最大延迟
                        delay = min(base_delay * (2 ** (attempt - 1)) + random.uniform(0, 3),
                                  self.config.web_crawler.max_delay)
                        await asyncio.sleep(delay)

                    # 动态调整爬虫参数
                    current_config = crawler_config.copy()
                    if attempt > 1:  # 第三次重试后增加超时和等待时间
                        current_config['page_timeout'] = min(current_config['page_timeout'] * 1.5, 180000)
                        current_config['wait_for'] = min(current_config['wait_for'] * 2, 15)
                        current_config['delay_before_return_html'] = min(current_config['delay_before_return_html'] * 2, 8)

                    # 使用缓存请求方法
                    result = await self._make_request_with_cache(
                        url=torrent.detail_url,
                        wait_for=current_config['wait_for'],
                        page_timeout=current_config['page_timeout'],
                        bypass_cache=True,
                        delay_before_return_html=current_config['delay_before_return_html'],
                        css_selector="body",
                        js_code="window.scrollTo(0, document.body.scrollHeight/2);" if attempt > 0 else None,
                        extra_http_headers={
                            'Referer': torrent.detail_url if attempt > 0 else crawler_config['headers']['Referer']
                        }
                    )

                    if not result.success:
                        error_msg = str(result.error_message) if result.error_message else "Unknown error"
                        if attempt < max_retries - 1:
                            continue
                        else:
                            raise Exception(f"抓取失败: {error_msg}")

                    # 提取磁力链接并解析文件名
                    magnet_link = await self._extract_magnet_from_content(result)

                    if magnet_link and validate_magnet_link(magnet_link):
                        torrent.magnet_link = magnet_link
                        torrent.status = "extracted"
                        self.stats['magnets_extracted'] += 1

                        # 检查是否重复并获取文件名
                        torrent_hash, torrent_name = parse_magnet(magnet_link)

                        # 仅当磁力链接包含更完整的文件名时才覆盖
                        if torrent_name and len(torrent_name) > len(torrent.title):
                            torrent.title = torrent_name
                        if torrent_hash and torrent_hash in self.processed_hashes:
                            torrent.status = "duplicate"
                            self.stats['duplicates_skipped'] += 1
                        elif torrent_hash:
                            self.processed_hashes.add(torrent_hash)

                        return torrent
                    else:
                        if attempt < max_retries - 1:
                            continue
                        else:
                            torrent.status = "failed"
                            self.stats['errors'] += 1
                            return torrent

                except Exception as e:
                    if attempt < max_retries - 1:
                        continue
                    else:
                        torrent.status = "failed"
                        self.stats['errors'] += 1
                        raise e

        return torrent

    async def _extract_magnet_links_sequential(self, torrents: List[TorrentInfo]) -> List[TorrentInfo]:
        """顺序提取磁力链接（原有逻辑）"""
        
        # 增强型详情页爬虫配置，使用配置参数
        crawler_config = {
            'verbose': False,
            'browser_type': 'chromium',
            'headless': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://www.google.com/',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            },
            'page_timeout': self.config.web_crawler.page_timeout,
            'wait_for': self.config.web_crawler.wait_for,
            'delay_before_return_html': self.config.web_crawler.delay_before_return,
            'proxy': self.config.web_crawler.proxy,
            'viewport': {'width': 1920, 'height': 1080},
            'timezone_id': 'Asia/Shanghai',
            'locale': 'zh-CN',
            'extra_http_headers': {
                'DNT': '1',
                'Sec-Ch-Ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
            }
        }
        
        for i, torrent in enumerate(torrents, 1):
                max_retries = self.config.web_crawler.max_retries
                base_delay = self.config.web_crawler.base_delay
                last_error = None

                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            # 指数退避 + 随机抖动，限制最大延迟
                            delay = min(base_delay * (2 ** (attempt - 1)) + random.uniform(0, 5),
                                      self.config.web_crawler.max_delay)
                            self.logger.info(f"🔄 [{i}/{len(torrents)}] 重试 {attempt+1}/{max_retries}, 等待 {delay:.1f} 秒: {torrent.title[:50]}...")
                            await asyncio.sleep(delay)
                        else:
                            self.logger.info(f"🔍 [{i}/{len(torrents)}] 提取磁力链接: {torrent.title[:50]}...")

                        # 动态调整爬虫参数
                        current_config = crawler_config.copy()
                        if attempt > 1:  # 第三次重试后增加超时和等待时间
                            current_config['page_timeout'] = min(current_config['page_timeout'] * 1.5, 180000)
                            current_config['wait_for'] = min(current_config['wait_for'] * 2, 15)
                            current_config['delay_before_return_html'] = min(current_config['delay_before_return_html'] * 2, 8)
                        
                        # 使用缓存请求方法
                        result = await self._make_request_with_cache(
                            url=torrent.detail_url,
                            wait_for=current_config['wait_for'],
                            page_timeout=current_config['page_timeout'],
                            bypass_cache=True,
                            delay_before_return_html=current_config['delay_before_return_html'],
                            css_selector="body",
                            js_code="window.scrollTo(0, document.body.scrollHeight/2);" if attempt > 0 else None,
                            extra_http_headers={
                                'Referer': torrent.detail_url if attempt > 0 else crawler_config['headers']['Referer']
                            }
                        )
                        
                        if not result.success:
                            error_msg = str(result.error_message) if result.error_message else "Unknown error"
                            if "ERR_CONNECTION_RESET" in error_msg or "Connection reset" in error_msg:
                                self.logger.warning(f"⚠️ 连接被重置，尝试 {attempt+1}/{max_retries}")
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(base_delay * (attempt + 1))  # 递增延迟
                                    continue
                            else:
                                self.logger.warning(f"⚠️ 抓取失败: {error_msg}")
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(base_delay)
                                    continue
                            break
                        
                        # 提取磁力链接并解析文件名
                        magnet_link = await self._extract_magnet_from_content(result)
                        
                        if magnet_link and validate_magnet_link(magnet_link):
                            torrent.magnet_link = magnet_link
                            torrent.status = "extracted"
                            self.stats['magnets_extracted'] += 1
                            
                            # 检查是否重复并获取文件名（保留原始标题用于显示）
                            torrent_hash, torrent_name = parse_magnet(magnet_link)
                            self.logger.debug(f"🔍 磁力链接解析 - 原始标题: {torrent.title} | 解析文件名: {torrent_name}")
                            
                            # 仅当磁力链接包含更完整的文件名时才覆盖
                            if torrent_name and len(torrent_name) > len(torrent.title):
                                torrent.title = torrent_name
                            if torrent_hash and torrent_hash in self.processed_hashes:
                                torrent.status = "duplicate"
                                self.stats['duplicates_skipped'] += 1
                                self.logger.info(f"⚠️ 跳过重复种子: {torrent.title[:50]}...")
                            elif torrent_hash:
                                self.processed_hashes.add(torrent_hash)
                            
                            self.logger.info(f"✅ 成功提取磁力链接: {torrent.title[:30]}...")
                            break  # 成功，跳出重试循环
                        else:
                            if attempt < max_retries - 1:
                                retry_delay = base_delay * (attempt + 1)
                                self.logger.warning(f"⚠️ 未找到磁力链接，重试 {attempt+1}/{max_retries}")
                                await asyncio.sleep(base_delay)
                                continue
                            else:
                                torrent.status = "failed"
                                self.stats['errors'] += 1
                                self.logger.warning(f"❌ 未找到有效磁力链接: {torrent.title[:50]}...")
                        
                    except Exception as e:
                        error_msg = str(e)
                        if "ERR_CONNECTION_RESET" in error_msg or "Connection reset" in error_msg:
                            self.logger.warning(f"⚠️ 连接重置错误，尝试 {attempt+1}/{max_retries}: {torrent.title[:50]}...")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(base_delay * (attempt + 1))
                                continue
                        else:
                            self.logger.error(f"❌ 提取失败: {torrent.title[:50]}... - {error_msg}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(base_delay)
                                continue
                        
                        # 最后一次尝试失败
                        if attempt == max_retries - 1:
                            torrent.status = "failed"
                            self.stats['errors'] += 1
                            break
                
                # 每个种子间的延迟，避免被检测为爬虫，使用配置参数
                if i < len(torrents):  # 不是最后一个
                    delay = self.config.web_crawler.inter_request_delay + random.uniform(0, 1)
                    await asyncio.sleep(delay)
        
        successful_extractions = len([t for t in torrents if t.status == "extracted"])
        self.logger.info(f"🎯 磁力链接提取完成: {successful_extractions}/{len(torrents)} 成功")
        
        return torrents
    
    async def _extract_magnet_from_content(self, crawl_result) -> Optional[str]:
        """从crawl4ai结果中提取磁力链接"""
        try:
            # 在文本内容中搜索磁力链接
            full_text = crawl_result.markdown + " " + crawl_result.cleaned_html
            
            # 磁力链接模式
            magnet_patterns = [
                r'magnet:\?xt=urn:btih:[0-9a-fA-F]{40}[^"\s]*',
                r'magnet:\?xt=urn:btih:[0-9a-zA-Z]{32}[^"\s]*'
            ]
            
            for pattern in magnet_patterns:
                matches = re.findall(pattern, full_text, re.IGNORECASE)
                if matches:
                    magnet_link = matches[0].replace('&amp;', '&')
                    return magnet_link
            
            # 如果文本搜索失败，使用HTML解析
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(crawl_result.cleaned_html, 'html.parser')
            
            # 查找下载链接
            download_links = soup.find_all('a', href=True)
            for link in download_links:
                href = link['href']
                if href.startswith('magnet:'):
                    return href.replace('&amp;', '&')
            
            # 查找文本区域中的磁力链接
            text_areas = soup.find_all(['textarea', 'input'])
            for area in text_areas:
                text = area.get('value', '') or area.get_text()
                if text.startswith('magnet:'):
                    return text.replace('&amp;', '&')
            
            return None
            
        except Exception as e:
            self.logger.error(f"提取磁力链接失败: {str(e)}")
            return None
    
    async def add_torrents_to_qbittorrent(self, torrents: List[TorrentInfo]) -> List[TorrentInfo]:
        """
        将种子批量添加到qBittorrent并处理分类、重命名等

        Args:
            torrents: 待添加的种子信息列表

        Returns:
            处理后的种子信息列表
        """
        if not torrents:
            return []

        self.logger.info(f"➕ 开始批量添加 {len(torrents)} 个种子到qBittorrent...")

        for torrent in torrents:
            if not torrent.magnet_link or torrent.status != "extracted":
                continue

            try:
                # 1. AI分类
                # 使用配置中的AI分类设置
                ai_classify_enabled = hasattr(self.config, 'ai_classify_torrents') and self.config.ai_classify_torrents
                if ai_classify_enabled and self.config.deepseek.api_key:
                    self.logger.info(f"🧠 正在为 '{torrent.title}' 进行AI分类...")
                    category = await self.ai_classifier.classify(torrent.title, self.config.categories)
                    torrent.category = category
                    self.logger.info(f"   - AI分类结果: '{category}'")
                else:
                    torrent.category = "other"
                
                # 2. 获取保存路径
                save_path = await self._get_category_save_path(torrent.category)

                # 3. 添加种子到qBittorrent (不进行重命名)
                success = await self.qbt_client.add_torrent(
                    torrent.magnet_link,
                    torrent.category,
                    # 使用配置中的暂停设置，如果没有则默认为False
                    paused=getattr(self.config, 'add_torrents_paused', False)
                )

                if success:
                    self.stats['torrents_added'] += 1
                    torrent.status = "added"
                    self.logger.info(f"✅ 成功添加种子: {torrent.title}")
                else:
                    # 可能是因为哈希已经存在
                    if await self.qbt_client._is_duplicate(torrent.magnet_link):
                        self.stats['duplicates_skipped'] += 1
                        torrent.status = "duplicate"
                        self.logger.warning(f"⚠️ 跳过重复的种子: {torrent.title}")
                    else:
                        self.stats['errors'] += 1
                        torrent.status = "failed"
                        self.logger.error(f"❌ 添加种子失败: {torrent.title}")

            except Exception as e:
                torrent.status = "failed"
                self.stats['errors'] += 1
                self.logger.error(f"❌ 处理种子 '{torrent.title}' 时发生意外错误: {e}")
                import traceback
                self.logger.debug(traceback.format_exc())

        # 批量完成后发送一次通知
        await self._notify_completion(torrents)
            
        return torrents
    
    async def _get_category_save_path(self, category: str) -> str:
        """获取分类的保存路径"""
        try:
            existing_categories = await self.qbt_client.get_existing_categories()
            if category in existing_categories:
                return existing_categories[category].get('savePath', '默认路径')
            elif category in self.config.categories:
                return self.config.categories[category].save_path
        except Exception:
            pass
        return "默认路径"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取爬虫统计信息"""
        return {
            'stats': self.stats.copy(),
            'processed_hashes_count': len(self.processed_hashes)
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.stats = {
            'pages_crawled': 0,
            'torrents_found': 0,
            'magnets_extracted': 0,
            'torrents_added': 0,
            'duplicates_skipped': 0,
            'errors': 0
        }
        self.processed_hashes.clear()
    
    async def _notify_completion(self, torrents: List[TorrentInfo]):
        """通知批量处理完成"""
        added_count = len([t for t in torrents if t.status == "added"])
        failed_count = len([t for t in torrents if t.status == "failed"])
        duplicate_count = len([t for t in torrents if t.status == "duplicate"])
        
        if self.config.notifications.console.enabled:
            if self.notification_manager.use_colors:
                from colorama import Fore, Style
                print(f"\n{Fore.GREEN}✅ 批量处理完成!")
                print(f"{Fore.CYAN}📊 处理结果:")
                print(f"   成功添加: {Fore.GREEN}{added_count}")
                print(f"   失败数量: {Fore.RED}{failed_count}")
                print(f"   重复跳过: {Fore.YELLOW}{duplicate_count}")
                print(f"{Fore.GREEN}{'─'*50}{Style.RESET_ALL}")
            else:
                print(f"\n✅ 批量处理完成!")
                print(f"📊 处理结果:")
                print(f"   成功添加: {added_count}")
                print(f"   失败数量: {failed_count}")
                print(f"   重复跳过: {duplicate_count}")
                print(f"{'─'*50}")

        # 发送通知
        try:
            await self.notification_manager.send_statistics({
                'total_processed': len(torrents),
                'successful_adds': added_count,
                'failed_adds': failed_count,
                'duplicates_skipped': duplicate_count,
                'ai_classifications': 0,  # 暂时设置为0
                'rule_classifications': 0,  # 暂时设置为0
                'url_crawls': 1,
                'batch_adds': 1 if added_count > 0 else 0
            })
        except Exception as e:
            self.logger.warning(f"发送完成通知失败: {str(e)}")

    async def extract_magnet_links_fallback(self, torrents: List[TorrentInfo]) -> List[TorrentInfo]:
        """
        备用方法：当详情页面抓取失败时的处理方案
        暂时标记所有种子为失败状态，并提供用户手动操作建议
        """
        self.logger.warning("🚨 由于网站反爬虫机制，暂时无法自动提取磁力链接")
        self.logger.info("💡 建议解决方案:")
        self.logger.info("   1. 手动访问种子详情页面")
        self.logger.info("   2. 复制磁力链接到剪贴板")
        self.logger.info("   3. 程序会自动检测并添加")
        
        # 标记所有种子为失败，但保留信息供用户参考
        for torrent in torrents:
            torrent.status = "failed"
            self.stats['errors'] += 1
            self.logger.info(f"📄 种子详情: {torrent.title[:60]}")
            self.logger.info(f"   URL: {torrent.detail_url}")
        
        return torrents


async def crawl_and_add_torrents(search_url: str, config: AppConfig, 
                                qbt_client: QBittorrentClient, 
                                max_pages: int = 1) -> Dict[str, Any]:
    """
    便捷函数：抓取并添加种子
    
    Args:
        search_url: 搜索页面URL
        config: 应用配置
        qbt_client: qBittorrent客户端
        max_pages: 最大抓取页数
        
    Returns:
        处理结果统计
    """
    crawler = WebCrawler(config, qbt_client)
    
    try:
        # 抓取搜索页面
        torrents = await crawler.crawl_xxxclub_search(search_url, max_pages)
        
        if not torrents:
            # 详细分析失败原因并提供指导
            crawler.logger.info("🔍 分析可能的问题:")
            crawler.logger.info("   ➤ 网站可能检测到自动化访问")
            crawler.logger.info("   ➤ 搜索关键词可能无结果")
            crawler.logger.info("   ➤ 网页结构可能发生变化")
            
            crawler.logger.info("🛠️ 建议尝试以下解决方案:")
            crawler.logger.info("   1. 手动打开浏览器访问搜索页面:")
            crawler.logger.info(f"      {search_url}")
            crawler.logger.info("   2. 检查是否需要验证码或登录")
            crawler.logger.info("   3. 如果能正常访问，请:")
            crawler.logger.info("      • 找到感兴趣的种子")
            crawler.logger.info("      • 点击进入种子详情页面")
            crawler.logger.info("      • 复制磁力链接到剪贴板")
            crawler.logger.info("      • 程序会自动检测并添加")
            crawler.logger.info("   4. 如果搜索无结果，尝试修改搜索关键词")
            
            return {
                'success': False,
                'message': '未找到任何种子 - 可能遇到反爬虫机制或搜索无结果',
                'search_url': search_url,
                'suggestions': [
                    '手动访问搜索页面确认内容',
                    '复制单个磁力链接到剪贴板',
                    '检查搜索关键词是否正确',
                    '确认网站是否可正常访问'
                ],
                'stats': crawler.get_stats()
            }
        
        # 提取磁力链接
        torrents = await crawler.extract_magnet_links(torrents)
        
        # 检查提取成功率，如果太低则提供备用方案
        extracted_count = len([t for t in torrents if t.status == "extracted"])
        total_count = len(torrents)
        success_rate = extracted_count / total_count if total_count > 0 else 0
        
        if success_rate < 0.1 and total_count > 5:  # 成功率低于10%且种子数量大于5
            crawler.logger.warning(f"🚨 磁力链接提取成功率过低 ({success_rate:.1%})，可能遇到反爬虫机制")
            crawler.logger.info("💡 为您提供种子详情页面链接，可手动复制磁力链接:")
            
            for i, torrent in enumerate(torrents[:10], 1):  # 只显示前10个
                crawler.logger.info(f"[{i}] {torrent.title[:60]}")
                crawler.logger.info(f"    {torrent.detail_url}")
                if i < len(torrents):
                    crawler.logger.info("")
            
            if len(torrents) > 10:
                crawler.logger.info(f"... 还有 {len(torrents) - 10} 个种子未显示")
            
            return {
                'success': False,
                'message': f'抓取受阻: 找到{total_count}个种子，但只能提取{extracted_count}个磁力链接。请手动访问详情页面复制磁力链接。',
                'torrents': [
                    {
                        'title': t.title,
                        'detail_url': t.detail_url,
                        'status': t.status,
                        'size': t.size
                    }
                    for t in torrents
                ],
                'stats': crawler.get_stats()
            }
        
        # 添加到qBittorrent
        torrents = await crawler.add_torrents_to_qbittorrent(torrents)
        
        stats = crawler.get_stats()
        
        return {
            'success': True,
            'message': f"处理完成: 找到{stats['stats']['torrents_found']}个种子，成功添加{stats['stats']['torrents_added']}个",
            'torrents': [
                {
                    'title': t.title,
                    'status': t.status,
                    'category': t.category,
                    'size': t.size
                }
                for t in torrents
            ],
            'stats': stats
        }
    except CrawlerError as e:
        # 专门处理爬虫错误，提供更详细的指导
        error_msg = str(e)
        crawler.logger.error("🚨 网页抓取遇到问题")
        
        if "ERR_CONNECTION_RESET" in error_msg:
            crawler.logger.info("🔍 诊断: 连接被重置")
            crawler.logger.info("📋 这通常表示:")
            crawler.logger.info("   • 网站检测到自动化访问并主动断开连接")
            crawler.logger.info("   • IP地址可能被临时限制")
            crawler.logger.info("   • 网站有较强的反爬虫保护")
            
            crawler.logger.info("🛠️ 解决方案:")
            crawler.logger.info("   1. 立即解决方案:")
            crawler.logger.info("      • 手动访问搜索页面")
            crawler.logger.info("      • 复制磁力链接到剪贴板")
            crawler.logger.info("      • 程序会自动添加")
            crawler.logger.info("   2. 长期解决方案:")
            crawler.logger.info("      • 使用VPN换IP")
            crawler.logger.info("      • 等待一段时间后重试")
            crawler.logger.info("      • 降低访问频率")
        else:
            crawler.logger.info("🔍 其他网络问题")
            crawler.logger.info("🛠️ 建议:")
            crawler.logger.info("   • 检查网络连接")
            crawler.logger.info("   • 确认网站是否可访问")
            crawler.logger.info("   • 尝试手动访问页面")
        
        return {
            'success': False,
            'message': f'网页抓取失败: {error_msg}',
            'error_type': 'crawler_error',
            'search_url': search_url,
            'stats': crawler.get_stats()
        }
    except Exception as e:
        # 处理其他未预期的错误
        crawler.logger.error(f"❌ 处理过程中出现未预期错误: {str(e)}")
        return {
            'success': False,
            'message': f'处理失败: {str(e)}',
            'error_type': 'unexpected_error',
            'stats': crawler.get_stats()
        }
    finally:
        # 确保清理WebCrawler资源
        await crawler.cleanup()
