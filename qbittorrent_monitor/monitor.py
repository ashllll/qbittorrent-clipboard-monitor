"""简化版剪贴板监控器"""

import asyncio
import logging
import re
from typing import Optional, Set, Callable
from dataclasses import dataclass
from datetime import datetime

import pyperclip

from .config import Config
from .qb_client import QBClient, parse_magnet
from .classifier import ContentClassifier


logger = logging.getLogger(__name__)


@dataclass
class MonitorStats:
    """监控统计"""
    total_processed: int = 0
    successful_adds: int = 0
    failed_adds: int = 0
    duplicates_skipped: int = 0
    start_time: Optional[datetime] = None
    
    @property
    def uptime_seconds(self) -> float:
        if self.start_time:
            return (datetime.now() - self.start_time).total_seconds()
        return 0.0


class ClipboardMonitor:
    """剪贴板监控器"""
    
    MAGNET_PATTERN = re.compile(r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+')
    
    def __init__(
        self,
        qb_client: QBClient,
        config: Config,
        classifier: Optional[ContentClassifier] = None,
    ):
        self.qb = qb_client
        self.config = config
        self.classifier = classifier or ContentClassifier(config)
        self.stats = MonitorStats()
        
        self._last_clip = ""
        self._processed: Set[str] = set()
        self._running = False
        self._handlers: list[Callable[[str, str], None]] = []
    
    def add_handler(self, handler: Callable[[str, str], None]) -> None:
        """添加处理回调 - 参数: (magnet, category)"""
        self._handlers.append(handler)
    
    async def start(self) -> None:
        """启动监控"""
        self._running = True
        self.stats.start_time = datetime.now()
        
        logger.info("=" * 50)
        logger.info("剪贴板监控已启动")
        logger.info(f"检查间隔: {self.config.check_interval}秒")
        logger.info("按 Ctrl+C 停止")
        logger.info("=" * 50)
        
        try:
            while self._running:
                await self._check_clipboard()
                await asyncio.sleep(self.config.check_interval)
        except asyncio.CancelledError:
            logger.info("监控已取消")
        finally:
            self._running = False
    
    def stop(self) -> None:
        """停止监控"""
        self._running = False
    
    async def _check_clipboard(self) -> None:
        """检查剪贴板内容"""
        try:
            current = pyperclip.paste()
            if not current or current == self._last_clip:
                return
            
            self._last_clip = current
            await self._process_content(current)
            
        except Exception as e:
            logger.error(f"检查剪贴板失败: {e}")
    
    async def _process_content(self, content: str) -> None:
        """处理剪贴板内容"""
        # 查找所有磁力链接
        magnets = self.MAGNET_PATTERN.findall(content)
        
        # 如果整个内容就是一个磁力链接
        if content.startswith("magnet:?"):
            magnets = [content]
        
        if not magnets:
            return
        
        logger.info(f"发现 {len(magnets)} 个磁力链接")
        
        for magnet in magnets:
            await self._process_magnet(magnet)
    
    async def _process_magnet(self, magnet: str) -> None:
        """处理单个磁力链接"""
        self.stats.total_processed += 1
        
        # 去重检查
        magnet_hash = self._extract_hash(magnet)
        if magnet_hash in self._processed:
            self.stats.duplicates_skipped += 1
            logger.debug(f"跳过重复: {magnet[:50]}...")
            return
        
        # 获取名称并分类
        name = parse_magnet(magnet) or magnet
        category = await self.classifier.classify(name)
        cat_config = self.config.categories.get(category)
        
        logger.info(f"分类结果: {name[:50]}... -> {category}")
        
        # 添加到qBittorrent
        success = await self.qb.add_torrent(
            magnet,
            category=category,
            save_path=cat_config.save_path if cat_config else None,
        )
        
        if success:
            self.stats.successful_adds += 1
            self._processed.add(magnet_hash)
            
            # 调用回调
            for handler in self._handlers:
                try:
                    handler(magnet, category)
                except Exception as e:
                    logger.error(f"处理回调失败: {e}")
        else:
            self.stats.failed_adds += 1
    
    def _extract_hash(self, magnet: str) -> str:
        """提取磁力链接的hash"""
        import re
        match = re.search(r'btih:([a-zA-Z0-9]+)', magnet, re.IGNORECASE)
        return match.group(1).lower() if match else magnet
    
    def get_stats(self) -> MonitorStats:
        """获取统计信息"""
        return self.stats
    
    def print_stats(self) -> None:
        """打印统计信息"""
        stats = self.stats
        logger.info("=" * 50)
        logger.info("监控统计")
        logger.info("=" * 50)
        logger.info(f"运行时间: {stats.uptime_seconds:.1f}秒")
        logger.info(f"处理总数: {stats.total_processed}")
        logger.info(f"成功添加: {stats.successful_adds}")
        logger.info(f"失败添加: {stats.failed_adds}")
        logger.info(f"跳过重复: {stats.duplicates_skipped}")
        logger.info("=" * 50)
