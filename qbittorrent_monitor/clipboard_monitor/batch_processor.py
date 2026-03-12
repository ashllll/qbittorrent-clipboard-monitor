"""智能批处理器 - 根据内容类型和系统负载智能调整批处理策略

此模块提供 SmartBatcher 类，用于批量处理剪贴板内容，
根据队列压力和系统负载动态调整批处理大小。
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Callable


logger = logging.getLogger(__name__)


class SmartBatcher:
    """智能批处理器 - 优化指导文档建议
    
    根据内容类型和系统负载智能调整批处理策略，
    自动调整批次大小以优化吞吐量。
    
    Attributes:
        max_size: 最大批次大小
        timeout: 批处理超时时间
        batch_queue: 批次队列
        processor: 批处理器函数
        stats: 批处理统计信息
    
    Example:
        >>> batcher = SmartBatcher(max_size=10, timeout=0.5)
        >>> batcher.set_processor(my_processor)
        >>> await batcher.add_to_batch(item)
    """
    
    def __init__(self, max_size: int = 10, timeout: float = 0.5):
        """初始化智能批处理器
        
        Args:
            max_size: 最大批次大小
            timeout: 批处理超时时间（秒）
        """
        self.max_size = max_size
        self.timeout = timeout
        self.batch_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=100)
        self.processor: Optional[Callable[[List[Dict[str, Any]], float], Any]] = None
        self._processing_task: Optional[asyncio.Task] = None
        self._shutdown = False
        self.stats = {
            'batches_processed': 0,
            'items_processed': 0,
            'avg_batch_size': 0.0,
            'queue_pressure': 0.0
        }
    
    def set_processor(self, processor: Callable[[List[Dict[str, Any]], float], Any]) -> None:
        """设置批处理器
        
        Args:
            processor: 处理批次的回调函数
        """
        self.processor = processor
    
    async def start(self) -> None:
        """启动批处理器"""
        if self._processing_task is None or self._processing_task.done():
            self._shutdown = False
            self._processing_task = asyncio.create_task(self._processing_loop())
            logger.debug("SmartBatcher 已启动")
    
    async def stop(self) -> None:
        """停止批处理器"""
        self._shutdown = True
        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        logger.debug("SmartBatcher 已停止")
    
    async def _processing_loop(self) -> None:
        """批处理主循环"""
        while not self._shutdown:
            try:
                await self._process_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"批处理循环出错: {e}")
                await asyncio.sleep(0.1)
    
    async def add_to_batch(self, item: Dict[str, Any]) -> bool:
        """添加项目到批次
        
        Args:
            item: 要添加的项目
        
        Returns:
            是否成功添加
        """
        try:
            self.batch_queue.put_nowait(item)
            await self._adjust_batch_size()
            return True
        except asyncio.QueueFull:
            logger.warning("批次队列已满，立即处理当前批次")
            await self._process_batch()
            try:
                self.batch_queue.put_nowait(item)
                return True
            except asyncio.QueueFull:
                logger.error("批次队列已满，无法添加项目")
                return False
    
    async def _process_batch(self) -> None:
        """处理当前批次"""
        if self.processor is None:
            logger.error("批处理器未设置")
            return
        
        items: List[Dict[str, Any]] = []
        batch_start_time = time.time()
        
        try:
            # 等待第一个项目
            first_item = await asyncio.wait_for(
                self.batch_queue.get(),
                timeout=0.1
            )
            items.append(first_item)
            
            # 收集更多项目直到达到最大批次大小或超时
            while len(items) < self.max_size:
                try:
                    item = await asyncio.wait_for(
                        self.batch_queue.get(),
                        timeout=self.timeout
                    )
                    items.append(item)
                except asyncio.TimeoutError:
                    break
        except asyncio.TimeoutError:
            return
        except Exception as e:
            logger.error(f"收集批次项目时出错: {e}")
            return
        
        if not items:
            return
        
        # 更新统计
        self.stats['batches_processed'] += 1
        self.stats['items_processed'] += len(items)
        
        total_items = self.stats['items_processed']
        total_batches = self.stats['batches_processed']
        self.stats['avg_batch_size'] = total_items / total_batches
        
        # 处理批次
        try:
            await self.processor(items, batch_start_time)
            logger.debug(
                f"批次处理完成: {len(items)} 个项目 "
                f"(用时: {time.time() - batch_start_time:.3f}s)"
            )
        except Exception as e:
            logger.error(f"批次处理失败: {e}")
    
    async def _adjust_batch_size(self) -> None:
        """动态调整批次大小"""
        current_size = self.batch_queue.qsize()
        queue_pressure = current_size / self.batch_queue.maxsize
        
        self.stats['queue_pressure'] = queue_pressure
        
        if queue_pressure > 0.8:
            self.max_size = min(20, self.max_size + 1)
        elif queue_pressure < 0.2:
            self.max_size = max(5, self.max_size - 1)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取批处理统计
        
        Returns:
            包含批处理统计信息的字典
        """
        return {
            **self.stats,
            'current_queue_size': self.batch_queue.qsize(),
            'current_batch_size': self.max_size,
            'timeout': self.timeout
        }
    
    def clear(self) -> None:
        """清空批次队列"""
        while not self.batch_queue.empty():
            try:
                self.batch_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        logger.debug("批次队列已清空")
