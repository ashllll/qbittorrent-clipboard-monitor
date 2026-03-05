"""剪贴板监控器"""

import asyncio
import logging
import re
from typing import Optional, Set, Callable
from dataclasses import dataclass
from datetime import datetime

import pyperclip

from .config import Config
from .qb_client import QBClient
from .classifier import ContentClassifier
from .utils import parse_magnet

logger = logging.getLogger(__name__)


@dataclass
class MonitorStats:
    """统计信息"""
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
    
    def __init__(self, qb_client: QBClient, config: Config, classifier: Optional[ContentClassifier] = None):
        self.qb = qb_client
        self.config = config
        self.classifier = classifier or ContentClassifier(config)
        self.stats = MonitorStats()
        self._last_clip = ""
        self._processed: Set[str] = set()
        self._running = False
        self._handlers: list = []
    
    def add_handler(self, handler: Callable[[str, str], None]) -> None:
        self._handlers.append(handler)
    
    async def start(self) -> None:
        """启动监控"""
        self._running = True
        self.stats.start_time = datetime.now()
        
        print("=" * 50)
        print("剪贴板监控已启动")
        print(f"检查间隔: {self.config.check_interval}秒")
        print("按 Ctrl+C 停止")
        print("=" * 50)
        
        try:
            while self._running:
                await self._check_clipboard()
                await asyncio.sleep(self.config.check_interval)
        except asyncio.CancelledError:
            logger.info("监控已取消")
        finally:
            self._running = False
    
    def stop(self) -> None:
        self._running = False
    
    async def _check_clipboard(self) -> None:
        try:
            current = pyperclip.paste()
            if not current or current == self._last_clip:
                return
            self._last_clip = current
            await self._process_content(current)
        except Exception as e:
            logger.error(f"检查剪贴板失败: {e}")
    
    async def _process_content(self, content: str) -> None:
        magnets = self.MAGNET_PATTERN.findall(content)
        if content.startswith("magnet:?"):
            magnets = [content]
        if not magnets:
            return
        
        logger.info(f"发现 {len(magnets)} 个磁力链接")
        for magnet in magnets:
            await self._process_magnet(magnet)
    
    async def _process_magnet(self, magnet: str) -> None:
        self.stats.total_processed += 1
        
        # 去重
        magnet_hash = self._extract_hash(magnet)
        if magnet_hash in self._processed:
            self.stats.duplicates_skipped += 1
            return
        
        # 分类
        name = parse_magnet(magnet) or magnet
        category = await self.classifier.classify(name)
        cat_config = self.config.categories.get(category)
        
        logger.info(f"分类: {name[:50]}... -> {category}")
        
        # 添加
        success = await self.qb.add_torrent(magnet, category=category, save_path=cat_config.save_path if cat_config else None)
        
        if success:
            self.stats.successful_adds += 1
            self._processed.add(magnet_hash)
            for handler in self._handlers:
                try:
                    handler(magnet, category)
                except Exception as e:
                    logger.error(f"回调失败: {e}")
        else:
            self.stats.failed_adds += 1
    
    def _extract_hash(self, magnet: str) -> str:
        match = re.search(r'btih:([a-zA-Z0-9]+)', magnet, re.IGNORECASE)
        return match.group(1).lower() if match else magnet
