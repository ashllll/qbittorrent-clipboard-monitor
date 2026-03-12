"""剪贴板监控器核心模块

此模块提供 ClipboardMonitor 类，实现剪贴板监控的核心功能，
包括剪贴板监控循环、事件处理、历史记录和统计。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, OrderedDict as OrderedDictType

import pyperclip

from .base import BaseClipboardMonitor, MonitorStats

if TYPE_CHECKING:
    from ..config import Config
    from ..qb_client import QBClient
    from ..classifier import ContentClassifier


logger = logging.getLogger(__name__)


@dataclass
class PacingConfig:
    """智能轮询配置"""
    active_interval: float = 0.5
    idle_interval: float = 3.0
    idle_threshold_seconds: float = 30.0
    burst_window_seconds: float = 5.0
    burst_threshold: int = 3


class MagnetExtractor:
    """优化的磁力链接提取器"""
    
    # 预编译正则表达式 - 性能优化
    MAGNET_PATTERN = re.compile(
        r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{32,40}',
        re.IGNORECASE
    )
    BTIH_PATTERN = re.compile(r'btih:([a-fA-F0-9]{40}|[a-z2-7]{32})', re.IGNORECASE)
    
    MIN_MAGNET_LENGTH = 50
    MAX_MAGNET_LENGTH = 2000
    
    @classmethod
    def extract(cls, content: str) -> List[str]:
        """从内容中提取所有磁力链接"""
        # 长度检查
        if not content or len(content) < cls.MIN_MAGNET_LENGTH:
            return []
        
        # 长度限制（防止DoS）
        if len(content) > cls.MAX_MAGNET_LENGTH * 10:
            logger.warning(f"剪贴板内容过长 ({len(content)} 字符)，可能被截断")
            content = content[:cls.MAX_MAGNET_LENGTH * 10]
        
        # 快速检查是否包含 magnet: 前缀
        if 'magnet:?' not in content:
            if content.startswith('magnet:?'):
                return cls._validate_and_return(content)
            return []
        
        # 使用预编译正则快速匹配
        magnets = cls.MAGNET_PATTERN.findall(content)
        
        # 去重并保持顺序，同时验证每个磁力链接
        seen = set()
        unique_magnets = []
        for m in magnets:
            magnet_hash = cls._extract_hash(m)
            if magnet_hash and magnet_hash not in seen:
                seen.add(magnet_hash)
                unique_magnets.append(m)
        
        return unique_magnets
    
    @classmethod
    def _validate_and_return(cls, content: str) -> List[str]:
        """验证并返回单个磁力链接"""
        if cls.BTIH_PATTERN.search(content):
            return [content]
        return []
    
    @classmethod
    def _extract_hash(cls, magnet: str) -> Optional[str]:
        """提取磁力链接的 hash"""
        match = cls.BTIH_PATTERN.search(magnet)
        return match.group(1).lower() if match else None


class ClipboardMonitor(BaseClipboardMonitor):
    """剪贴板监控器 - 核心实现
    
    实现剪贴板监控的核心功能，包括：
    - 剪贴板内容监控
    - 磁力链接提取和处理
    - 分类和添加到 qBittorrent
    - 统计和历史记录
    
    Attributes:
        qb: qBittorrent 客户端
        config: 应用配置
        classifier: 内容分类器
        stats: 监控统计
        pacing: 轮询配置
    
    Example:
        >>> from qbittorrent_monitor.clipboard_monitor import ClipboardMonitor
        >>> monitor = ClipboardMonitor(qb_client, config)
        >>> await monitor.start()
    """
    
    def __init__(
        self,
        qb_client: QBClient,
        config: Config,
        classifier: Optional[ContentClassifier] = None,
        pacing_config: Optional[PacingConfig] = None,
    ):
        """初始化剪贴板监控器
        
        Args:
            qb_client: qBittorrent 客户端
            config: 应用配置
            classifier: 内容分类器（可选）
            pacing_config: 轮询配置（可选）
        """
        self.qb = qb_client
        self.config = config
        self.classifier = classifier
        self.pacing = pacing_config or PacingConfig()
        
        # 统计信息
        self.stats = MonitorStats()
        
        # 已处理缓存（LRU）
        self._processed: OrderedDictType[str, None] = OrderedDict()
        self._max_processed_size = 10000
        
        self._handlers: List[Callable[[str, str], None]] = []
        
        # 运行状态
        self._running = False
        self._last_content: str = ""
        self._last_content_hash: str = ""
        self._last_change_time: float = 0.0
        self._change_count_in_window: int = 0
        self._window_start_time: float = 0.0
        
        # 速率限制
        self._max_magnets_per_check = 100
    
    def add_handler(self, handler: Callable[[str, str], None]) -> None:
        """添加处理回调
        
        Args:
            handler: 回调函数，接收 (magnet, category) 参数
        """
        self._handlers.append(handler)
    
    def remove_handler(self, handler: Callable[[str, str], None]) -> None:
        """移除处理回调
        
        Args:
            handler: 要移除的回调函数
        """
        if handler in self._handlers:
            self._handlers.remove(handler)
    
    def get_status(self) -> Dict[str, any]:
        """获取监控状态
        
        Returns:
            包含监控状态的字典
        """
        return {
            'running': self._running,
            'stats': {
                'total_processed': self.stats.total_processed,
                'successful_adds': self.stats.successful_adds,
                'failed_adds': self.stats.failed_adds,
                'duplicates_skipped': self.stats.duplicates_skipped,
            },
            'processed_count': len(self._processed),
            'last_change_time': self._last_change_time,
        }
    
    async def start(self) -> None:
        """启动监控"""
        self._running = True
        self._window_start_time = datetime.now().timestamp()
        
        logger.info("=" * 50)
        logger.info("剪贴板监控已启动")
        logger.info(f"活跃检查间隔: {self.pacing.active_interval}秒")
        logger.info(f"空闲检查间隔: {self.pacing.idle_interval}秒")
        logger.info("=" * 50)
        
        try:
            while self._running:
                check_start = datetime.now().timestamp()
                
                await self._check_clipboard()
                
                check_duration = (datetime.now().timestamp() - check_start) * 1000
                
                # 智能轮询间隔计算
                interval = self._calculate_interval()
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logger.info("监控已取消")
        finally:
            self._running = False
    
    def stop(self) -> None:
        """停止监控"""
        self._running = False
        logger.info("剪贴板监控已停止")
    
    async def cleanup(self) -> None:
        """清理资源"""
        self._processed.clear()
        self._handlers.clear()
        logger.debug("ClipboardMonitor 资源已清理")
    
    def _calculate_interval(self) -> float:
        """计算智能轮询间隔"""
        now = datetime.now().timestamp()
        time_since_last_change = now - self._last_change_time
        
        # 如果在突发窗口内有多次变化，使用活跃间隔
        if self._change_count_in_window >= self.pacing.burst_threshold:
            return self.pacing.active_interval
        
        # 如果窗口过期，重置计数
        if now - self._window_start_time > self.pacing.burst_window_seconds:
            self._change_count_in_window = 0
            self._window_start_time = now
        
        # 根据空闲状态选择间隔
        if time_since_last_change > self.pacing.idle_threshold_seconds:
            return self.pacing.idle_interval
        
        return self.pacing.active_interval
    
    async def _check_clipboard(self) -> None:
        """检查剪贴板"""
        try:
            # 异步读取剪贴板
            loop = asyncio.get_event_loop()
            current = await asyncio.wait_for(
                loop.run_in_executor(None, pyperclip.paste),
                timeout=0.5
            )
            
            if not current:
                return
            
            if current == self._last_content:
                return
            
            # 计算内容哈希
            content_hash = hashlib.md5(current.encode('utf-8')).hexdigest()
            
            if content_hash == self._last_content_hash:
                self._last_content = current
                return
            
            # 更新状态
            self._last_content = current
            self._last_content_hash = content_hash
            self._update_activity_tracking()
            
            # 处理内容
            await self._process_content(current)
            
        except Exception as e:
            logger.error(f"检查剪贴板失败: {e}")
    
    def _update_activity_tracking(self) -> None:
        """更新活动追踪状态"""
        now = datetime.now().timestamp()
        
        self._last_change_time = now
        
        if now - self._window_start_time <= self.pacing.burst_window_seconds:
            self._change_count_in_window += 1
        else:
            self._change_count_in_window = 1
            self._window_start_time = now
    
    async def _process_content(self, content: str) -> None:
        """处理剪贴板内容"""
        # 使用优化的磁力链接提取
        magnets = MagnetExtractor.extract(content)
        
        if not magnets:
            return
        
        # 速率限制检查
        if len(magnets) > self._max_magnets_per_check:
            logger.warning(
                f"检测到过多磁力链接 ({len(magnets)} > {self._max_magnets_per_check})，"
                f"仅处理前 {self._max_magnets_per_check} 个"
            )
            magnets = magnets[:self._max_magnets_per_check]
        
        logger.info(f"发现 {len(magnets)} 个磁力链接")
        
        for magnet in magnets:
            await self._process_magnet(magnet)
    
    async def _process_magnet(self, magnet: str) -> None:
        """处理单个磁力链接"""
        self.stats.total_processed += 1
        
        # 提取 hash
        magnet_hash = MagnetExtractor._extract_hash(magnet) or magnet
        
        # 已处理检查
        if magnet_hash in self._processed:
            logger.debug(f"磁力链接已处理过，跳过: {magnet[:50]}...")
            self.stats.duplicates_skipped += 1
            return
        
        # 分类
        category = "default"
        if self.classifier:
            try:
                classification_result = await self.classifier.classify(magnet)
                category = classification_result.category
            except Exception as e:
                logger.warning(f"分类失败: {e}")
        
        # 获取分类配置
        cat_config = None
        if hasattr(self.config, 'categories'):
            cat_config = self.config.categories.get(category)
        
        logger.info(f"分类: {magnet[:50]}... -> {category}")
        
        # 添加到 qBittorrent
        try:
            success = await self.qb.add_torrent(
                magnet,
                category=category,
                save_path=cat_config.save_path if cat_config else None
            )
            
            if success:
                self.stats.successful_adds += 1
                # 添加到已处理集合
                self._processed[magnet_hash] = None
                # 自动清理旧记录
                while len(self._processed) > self._max_processed_size:
                    self._processed.popitem(last=False)
                
                # 触发回调
                for handler in self._handlers:
                    try:
                        handler(magnet, category)
                    except Exception as e:
                        logger.error(f"回调失败: {e}")
            else:
                self.stats.failed_adds += 1
                
        except Exception as e:
            logger.error(f"添加种子失败: {e}")
            self.stats.failed_adds += 1
