"""优化版剪贴板监控器

此模块提供 OptimizedClipboardMonitor 类，继承自 ClipboardMonitor，
添加了智能活动跟踪、批处理和高级统计功能。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .core import ClipboardMonitor, MagnetExtractor, PacingConfig
from .activity_tracker import ActivityTracker
from .batch_processor import SmartBatcher

if TYPE_CHECKING:
    from ..config import Config
    from ..qb_client import QBClient
    from ..classifier import ContentClassifier


logger = logging.getLogger(__name__)


@dataclass
class AdvancedStats:
    """高级统计信息"""
    start_time: Optional[datetime] = None
    checks_performed: int = 0
    clipboard_changes: int = 0
    avg_check_time_ms: float = 0.0
    _check_times: List[float] = field(default_factory=list)
    
    def record_check_time(self, duration_ms: float) -> None:
        """记录单次检查耗时"""
        self._check_times.append(duration_ms)
        # 保持最近100次
        if len(self._check_times) > 100:
            self._check_times = self._check_times[-100:]
        self.avg_check_time_ms = sum(self._check_times) / len(self._check_times)
    
    @property
    def checks_per_minute(self) -> float:
        """计算每分钟检查次数"""
        if self.start_time:
            uptime = (datetime.now() - self.start_time).total_seconds()
            if uptime > 0:
                return (self.checks_performed / uptime) * 60
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            'checks_performed': self.checks_performed,
            'clipboard_changes': self.clipboard_changes,
            'avg_check_time_ms': round(self.avg_check_time_ms, 3),
            'checks_per_minute': round(self.checks_per_minute, 2),
        }


class OptimizedClipboardMonitor(ClipboardMonitor):
    """优化版剪贴板监控器
    
    继承自 ClipboardMonitor，添加了以下功能：
    - 智能活动跟踪（ActivityTracker）
    - 智能批处理（SmartBatcher）
    - 高级统计信息
    - 自适应监控策略
    
    Attributes:
        activity_tracker: 活动跟踪器
        smart_batcher: 智能批处理器
        advanced_stats: 高级统计信息
    
    Example:
        >>> from qbittorrent_monitor.clipboard_monitor import OptimizedClipboardMonitor
        >>> monitor = OptimizedClipboardMonitor(qb_client, config)
        >>> await monitor.start()
    """
    
    def __init__(
        self,
        qb_client: QBClient,
        config: Config,
        classifier: Optional[ContentClassifier] = None,
        pacing_config: Optional[PacingConfig] = None,
    ):
        """初始化优化版剪贴板监控器
        
        Args:
            qb_client: qBittorrent 客户端
            config: 应用配置
            classifier: 内容分类器（可选）
            pacing_config: 轮询配置（可选）
        """
        super().__init__(qb_client, config, classifier, pacing_config)
        
        # 智能组件
        self.activity_tracker = ActivityTracker(window_size=100)
        self.smart_batcher = SmartBatcher(max_size=10, timeout=0.5)
        
        # 设置批处理器
        self.smart_batcher.set_processor(self._process_batch_items)
        
        # 高级统计
        self.advanced_stats = AdvancedStats()
        
        # 批处理模式开关
        self._batch_mode = True
    
    async def start(self) -> None:
        """启动监控（优化版）"""
        # 启动批处理器
        if self._batch_mode:
            await self.smart_batcher.start()
        
        self.advanced_stats.start_time = datetime.now()
        self._running = True
        self._window_start_time = datetime.now().timestamp()
        
        logger.info("=" * 50)
        logger.info("优化版剪贴板监控已启动")
        logger.info(f"活跃检查间隔: {self.pacing.active_interval}秒")
        logger.info(f"空闲检查间隔: {self.pacing.idle_interval}秒")
        logger.info(f"批处理模式: {'启用' if self._batch_mode else '禁用'}")
        logger.info("=" * 50)
        
        try:
            while self._running:
                check_start = datetime.now().timestamp()
                
                await self._check_clipboard()
                
                self.advanced_stats.checks_performed += 1
                
                check_duration = (datetime.now().timestamp() - check_start) * 1000
                self.advanced_stats.record_check_time(check_duration)
                
                # 记录活动
                self.activity_tracker.record_activity(has_content=False)
                
                # 根据活动级别调整间隔
                interval = self._calculate_adaptive_interval()
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logger.info("监控已取消")
        finally:
            await self.cleanup()
    
    async def cleanup(self) -> None:
        """清理资源"""
        await self.smart_batcher.stop()
        self.activity_tracker.reset()
        await super().cleanup()
        logger.debug("OptimizedClipboardMonitor 资源已清理")
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控状态（包含高级统计）"""
        status = super().get_status()
        status.update({
            'advanced_stats': self.advanced_stats.to_dict(),
            'activity_tracker': self.activity_tracker.get_stats(),
            'batch_processor': self.smart_batcher.get_stats(),
        })
        return status
    
    def get_advanced_stats(self) -> Dict[str, Any]:
        """获取高级统计信息
        
        Returns:
            包含高级统计信息的字典
        """
        return {
            'monitor': self.advanced_stats.to_dict(),
            'activity': self.activity_tracker.get_stats(),
            'batch': self.smart_batcher.get_stats(),
            'base': {
                'total_processed': self.stats.total_processed,
                'successful_adds': self.stats.successful_adds,
                'failed_adds': self.stats.failed_adds,
                'duplicates_skipped': self.stats.duplicates_skipped,
            }
        }
    
    def _calculate_adaptive_interval(self) -> float:
        """计算自适应轮询间隔
        
        根据活动级别和智能轮询配置计算间隔。
        
        Returns:
            轮询间隔（秒）
        """
        base_interval = self._calculate_interval()
        
        # 根据活动级别微调
        activity_level = self.activity_tracker.current_level
        if activity_level >= 8:
            # 高活动时使用更短间隔
            return min(base_interval * 0.5, 0.1)
        elif activity_level <= 2:
            # 低活动时使用更长间隔
            return max(base_interval * 1.5, self.pacing.idle_interval)
        
        return base_interval
    
    async def _check_clipboard(self) -> None:
        """检查剪贴板（优化版）"""
        try:
            # 异步读取剪贴板
            loop = asyncio.get_event_loop()
            current = await asyncio.wait_for(
                loop.run_in_executor(None, __import__('pyperclip').paste),
                timeout=0.5
            )
            
            if not current:
                return
            
            if current == self._last_content:
                return
            
            # 计算内容哈希
            import hashlib
            content_hash = hashlib.md5(current.encode('utf-8')).hexdigest()
            
            if content_hash == self._last_content_hash:
                self._last_content = current
                return
            
            # 更新状态
            self._last_content = current
            self._last_content_hash = content_hash
            self._update_activity_tracking()
            self.advanced_stats.clipboard_changes += 1
            
            # 记录活动
            self.activity_tracker.record_activity(has_content=True)
            
            # 处理内容
            await self._process_content(current)
            
        except Exception as e:
            logger.error(f"检查剪贴板失败: {e}")
    
    async def _process_content(self, content: str) -> None:
        """处理剪贴板内容（优化版）"""
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
        
        # 使用批处理模式
        if self._batch_mode and len(magnets) > 1:
            for magnet in magnets:
                await self.smart_batcher.add_to_batch({
                    'magnet': magnet,
                    'source': 'clipboard'
                })
        else:
            # 单条处理
            for magnet in magnets:
                await self._process_magnet(magnet)
    
    async def _process_batch_items(
        self,
        items: List[Dict[str, Any]],
        batch_start_time: float
    ) -> None:
        """处理批次项目
        
        Args:
            items: 批次中的项目列表
            batch_start_time: 批次开始时间
        """
        logger.debug(f"处理批次: {len(items)} 个项目")
        
        for item in items:
            magnet = item.get('magnet')
            if magnet:
                await self._process_magnet(magnet)
    
    def enable_batch_mode(self, enabled: bool = True) -> None:
        """启用/禁用批处理模式
        
        Args:
            enabled: 是否启用批处理
        """
        self._batch_mode = enabled
        logger.info(f"批处理模式: {'启用' if enabled else '禁用'}")
    
    def reset_stats(self) -> None:
        """重置所有统计"""
        self.stats.total_processed = 0
        self.stats.successful_adds = 0
        self.stats.failed_adds = 0
        self.stats.duplicates_skipped = 0
        self.advanced_stats = AdvancedStats()
        self.advanced_stats.start_time = datetime.now()
        self.activity_tracker.reset()
        logger.info("统计信息已重置")
