"""
Playwright 爬虫模块

提供基于 Playwright 的增强型网页爬取功能:
1. 动态页面渲染支持
2. 磁力链接提取
3. 批量爬取
4. 反检测策略

安装:
    pip install playwright
    playwright install chromium

文档: https://playwright.dev/python/
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from urllib.parse import urlparse, urljoin

from .config import AppConfig, WebCrawlerConfig
from .qbittorrent_client import QBittorrentClient
from .utils import parse_magnet, validate_magnet_link


class MagnetExtractor:
    """磁力链接提取器"""
    
    # 匹配 magnet 链接的正则
    MAGNET_PATTERN = re.compile(
        r'magnet:\?xt=urn:[a-z0-9]+:[a-zA-Z0-9]{32,}',
        re.IGNORECASE
    )
    
    # 匹配各种协议的链接
    PROTOCOL_PATTERNS = {
        'magnet': re.compile(r'magnet:\?xt=urn:[a-z0-9]+:[a-zA-Z0-9]{32,}', re.IGNORECASE),
        'thunder': re.compile(r'thunder://[A-Za-z0-9+/=]+', re.IGNORECASE),
        'flashget': re.compile(r'flashget://[A-Za-z0-9+/=]+', re.IGNORECASE),
        'qqdl': re.compile(r'qqdl://[A-Za-z0-9+/=]+', re.IGNORECASE),
    }
    
    @classmethod
    async def extract_from_html(cls, html: str) -> List[str]:
        """从 HTML 中提取磁力链接"""
        magnets = set()
        
        # 查找所有 magnet 链接
        for match in cls.MAGNET_PATTERN.finditer(html):
            magnet = match.group(0)
            if validate_magnet_link(magnet):
                magnets.add(magnet)
        
        return list(magnets)
    
    @classmethod
    async def extract_from_text(cls, text: str) -> List[str]:
        """从纯文本中提取磁力链接"""
        magnets = set()
        
        for match in cls.MAGNET_PATTERN.finditer(text):
            magnet = match.group(0)
            if validate_magnet_link(magnet):
                magnets.add(magnet)
        
        return list(magnets)


class PlaywrightCrawler:
    """
    基于 Playwright 的网页爬虫
    
    特性:
    - JavaScript 渲染支持
    - 反检测措施
    - 磁力链接自动提取
    - 批量处理
    """
    
    def __init__(self, config: AppConfig, qbt_client: Optional[QBittorrentClient] = None):
        self.config = config
        self.qbt_client = qbt_client
        self.web_config: WebCrawlerConfig = config.web_crawler
        self.logger = logging.getLogger('PlaywrightCrawler')
        
        # 检查 Playwright 是否可用
        self._playwright = None
        self._browser = None
        self._context = None
        
        # 提取器
        self.extractor = MagnetExtractor()
        
        # 统计
        self.stats = {
            'pages_crawled': 0,
            'torrents_found': 0,
            'errors': 0,
            'start_time': None
        }
        
        # 反检测配置
        self._stealth_mode = True
        self._user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
    
    async def _get_browser(self):
        """获取或初始化浏览器"""
        if self._browser is None:
            try:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                
                # 启动浏览器 (headless 模式)
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                    ]
                )
                
                # 创建上下文 (隐私模式)
                self._context = await self._browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=random.choice(self._user_agents),
                )
                
                self.logger.info("Playwright 浏览器已启动")
                
            except ImportError:
                self.logger.error("Playwright 未安装，请运行: pip install playwright && playwright install chromium")
                raise
    
    async def _close_browser(self):
        """关闭浏览器"""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self.logger.info("Playwright 浏览器已关闭")
    
    async def crawl_page(self, url: str) -> Dict[str, Any]:
        """
        爬取单个页面
        
        Returns:
            {
                'url': str,
                'html': str,
                'magnets': List[str],
                'title': str,
                'success': bool,
                'error': str
            }
        """
        result = {
            'url': url,
            'html': '',
            'magnets': [],
            'title': '',
            'success': False,
            'error': ''
        }
        
        try:
            await self._get_browser()
            
            # 创建新页面
            page = await self._context.new_page()
            
            # 设置超时
            timeout = self.web_config.page_timeout
            
            # 导航到页面
            response = await page.goto(url, timeout=timeout, wait_until='networkidle')
            
            # 检查响应状态
            if response and response.status >= 400:
                result['error'] = f"HTTP {response.status}"
                self.stats['errors'] += 1
                await page.close()
                return result
            
            # 等待页面加载完成
            await page.wait_for_load_state('domcontentloaded')
            
            # 等待额外时间 (JS渲染)
            await asyncio.sleep(self.web_config.wait_for)
            
            # 获取 HTML
            result['html'] = await page.content()
            
            # 获取标题
            result['title'] = await page.title()
            
            # 提取磁力链接
            result['magnets'] = await self.extractor.extract_from_html(result['html'])
            
            result['success'] = True
            self.stats['pages_crawled'] += 1
            self.stats['torrents_found'] += len(result['magnets'])
            
            await page.close()
            
        except Exception as e:
            result['error'] = str(e)
            self.stats['errors'] += 1
            self.logger.error(f"爬取失败 {url}: {e}")
        
        return result
    
    async def crawl_and_extract(self, url: str) -> List[str]:
        """
        爬取页面并提取磁力链接
        
        简化接口，直接返回磁力链接列表
        """
        result = await self.crawl_page(url)
        if result['success']:
            return result['magnets']
        return []
    
    async def crawl_multiple(
        self,
        urls: List[str],
        max_concurrent: int = 3,
        on_progress: Optional[callable] = None
    ) -> List[Dict[str, Any]]:
        """
        批量爬取多个页面
        
        Args:
            urls: URL 列表
            max_concurrent: 最大并发数
            on_progress: 进度回调 (current, total, result)
        
        Returns:
            每个页面的结果列表
        """
        results = []
        self.stats['start_time'] = datetime.now()
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def crawl_with_semaphore(url: str, index: int):
            async with semaphore:
                result = await self.crawl_page(url)
                if on_progress:
                    on_progress(index + 1, len(urls), result)
                return result
        
        # 并发执行
        tasks = [crawl_with_semaphore(url, i) for i, url in enumerate(urls)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({
                    'url': urls[i],
                    'success': False,
                    'error': str(result),
                    'magnets': []
                })
                self.stats['errors'] += 1
            else:
                final_results.append(result)
        
        return final_results
    
    async def crawl_with_pagination(
        self,
        base_url: str,
        page_param: str = 'page',
        max_pages: int = 5,
        **kwargs
    ) -> List[str]:
        """
        分页爬取
        
        自动翻页爬取多个页面
        """
        all_magnets = []
        
        for page in range(1, max_pages + 1):
            # 构建 URL
            if '?' in base_url:
                url = f"{base_url}&{page_param}={page}"
            else:
                url = f"{base_url}?{page_param}={page}"
            
            self.logger.info(f"爬取第 {page}/{max_pages} 页: {url}")
            
            magnets = await self.crawl_and_extract(url)
            all_magnets.extend(magnets)
            
            # 页面间延迟
            await asyncio.sleep(self.web_config.inter_request_delay)
        
        # 去重
        return list(set(all_magnets))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        
        if stats['start_time']:
            elapsed = (datetime.now() - stats['start_time']).total_seconds()
            stats['elapsed_seconds'] = elapsed
            if elapsed > 0:
                stats['pages_per_second'] = stats['pages_crawled'] / elapsed
        
        return stats
    
    async def cleanup(self):
        """清理资源"""
        await self._close_browser()


# =========================================================================
# 便捷函数
# =========================================================================

async def quick_extract_magnets(url: str, **kwargs) -> List[str]:
    """
    快速提取页面中的磁力链接
    
    简化用法:
        magnets = await quick_extract_magnets("https://example.com")
    """
    config = AppConfig(
        qbittorrent=None,
        deepseek=None,
        categories={},
        web_crawler=WebCrawlerConfig(**kwargs)
    )
    
    crawler = PlaywrightCrawler(config)
    try:
        return await crawler.crawl_and_extract(url)
    finally:
        await crawler.cleanup()


async def quick_crawl(url: str, **kwargs) -> Dict[str, Any]:
    """
    快速爬取页面
    
    返回完整结果:
        result = await quick_crawl("https://example.com")
        print(result['magnets'])
        print(result['title'])
    """
    config = AppConfig(
        qbittorrent=None,
        deepseek=None,
        categories={},
        web_crawler=WebCrawlerConfig(**kwargs)
    )
    
    crawler = PlaywrightCrawler(config)
    try:
        return await crawler.crawl_page(url)
    finally:
        await crawler.cleanup()
