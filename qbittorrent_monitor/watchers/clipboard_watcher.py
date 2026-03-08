"""剪贴板观察器模块

提供纯剪贴板内容的观察和事件通知。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Set
from datetime import datetime

import pyperclip

logger = logging.getLogger(__name__)


@dataclass
class ClipboardEvent:
    """剪贴板变化事件
    
    Attributes:
        content: 剪贴板内容
        content_hash: 内容哈希
        timestamp: 事件时间戳
        change_count: 连续变化计数
    """
    content: str
    content_hash: str
    timestamp: float
    change_count: int = 1


class ClipboardWatcher:
    """剪贴板观察器
    
    纯剪贴板内容观察，负责：
    - 定期检查剪贴板内容
    - 检测内容变化
    - 触发变化事件
    
    不负责业务逻辑（磁力链接提取、处理等）。
    
    Attributes:
        check_interval: 检查间隔（秒）
        on_change: 变化回调函数列表
    
    Example:
        >>> async def on_clipboard_change(event: ClipboardEvent):
        ...     print(f"剪贴板变化: {event.content[:50]}")
        ...
        >>> watcher = ClipboardWatcher(check_interval=0.5)
        >>> watcher.add_listener(on_clipboard_change)
        >>> await watcher.start()
    """

    def __init__(
        self,
        check_interval: float = 1.0,
        read_timeout: float = 0.5,
    ):
        """初始化剪贴板观察器
        
        Args:
            check_interval: 检查间隔（秒）
            read_timeout: 剪贴板读取超时（秒）
        """
        self.check_interval = check_interval
        self.read_timeout = read_timeout
        
        self._running = False
        self._listeners: List[Callable[[ClipboardEvent], None]] = []
        
        # 状态跟踪
        self._last_content: str = ""
        self._last_hash: str = ""
        self._last_change_time: float = 0.0
        self._change_count: int = 0
        
        # 统计
        self._stats = {
            "checks": 0,
            "changes": 0,
            "errors": 0,
            "empty_skips": 0,
        }

    def add_listener(self, callback: Callable[[ClipboardEvent], None]) -> None:
        """添加变化监听器
        
        Args:
            callback: 变化时调用的回调函数
        """
        self._listeners.append(callback)
        logger.debug(f"添加剪贴板监听器，当前共 {len(self._listeners)} 个")

    def remove_listener(self, callback: Callable[[ClipboardEvent], None]) -> bool:
        """移除变化监听器
        
        Args:
            callback: 要移除的回调函数
            
        Returns:
            是否成功移除
        """
        if callback in self._listeners:
            self._listeners.remove(callback)
            logger.debug(f"移除剪贴板监听器，当前共 {len(self._listeners)} 个")
            return True
        return False

    async def start(self) -> None:
        """启动观察
        
        这是一个阻塞调用，会持续运行直到调用 stop()。
        """
        self._running = True
        logger.info(f"剪贴板观察器已启动，检查间隔: {self.check_interval}秒")
        
        try:
            while self._running:
                await self._check_once()
                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            logger.debug("剪贴板观察器已取消")
        finally:
            self._running = False
            logger.info("剪贴板观察器已停止")

    def stop(self) -> None:
        """停止观察"""
        self._running = False

    async def _check_once(self) -> None:
        """执行一次检查"""
        self._stats["checks"] += 1
        
        try:
            # 异步读取剪贴板
            content = await self._read_clipboard()
            
            if content is None:
                self._stats["empty_skips"] += 1
                return
            
            # 快速字符串比较
            if content == self._last_content:
                return
            
            # 计算哈希
            content_hash = self._compute_hash(content)
            
            # 如果哈希相同，跳过
            if content_hash == self._last_hash:
                self._last_content = content  # 更新内容避免重复计算哈希
                return
            
            # 检测连续变化
            now = time.time()
            if now - self._last_change_time < 5.0:  # 5秒内算连续变化
                self._change_count += 1
            else:
                self._change_count = 1
            
            # 更新状态
            self._last_content = content
            self._last_hash = content_hash
            self._last_change_time = now
            self._stats["changes"] += 1
            
            # 创建事件
            event = ClipboardEvent(
                content=content,
                content_hash=content_hash,
                timestamp=now,
                change_count=self._change_count
            )
            
            # 通知监听器
            await self._notify_listeners(event)
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"检查剪贴板失败: {e}")

    async def _read_clipboard(self) -> Optional[str]:
        """异步读取剪贴板内容
        
        Returns:
            剪贴板内容，如果为空或读取失败返回 None
        """
        try:
            loop = asyncio.get_event_loop()
            content = await asyncio.wait_for(
                loop.run_in_executor(None, pyperclip.paste),
                timeout=self.read_timeout
            )
            
            if not content or not isinstance(content, str):
                return None
            
            return content
            
        except asyncio.TimeoutError:
            logger.warning("读取剪贴板超时")
            return None
        except Exception as e:
            logger.error(f"读取剪贴板失败: {e}")
            return None

    async def _notify_listeners(self, event: ClipboardEvent) -> None:
        """通知所有监听器
        
        Args:
            event: 剪贴板变化事件
        """
        for listener in self._listeners:
            try:
                # 支持同步和异步回调
                result = listener(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"剪贴板监听器执行失败: {e}")

    def _compute_hash(self, content: str) -> str:
        """计算内容哈希
        
        使用 MD5 获得更好性能（监控场景不需要加密安全）。
        
        Args:
            content: 内容字符串
            
        Returns:
            MD5 哈希字符串
        """
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息
        
        Returns:
            统计字典
        """
        return self._stats.copy()

    def get_last_content(self) -> str:
        """获取最后的内容
        
        Returns:
            最后读取的剪贴板内容
        """
        return self._last_content

    def get_last_change_time(self) -> float:
        """获取最后变化时间
        
        Returns:
            最后变化的时间戳
        """
        return self._last_change_time

    def is_running(self) -> bool:
        """检查是否正在运行
        
        Returns:
            是否正在运行
        """
        return self._running


class SmartClipboardWatcher(ClipboardWatcher):
    """智能剪贴板观察器
    
    根据活动状态自动调整检查间隔。
    
    Attributes:
        active_interval: 活跃状态检查间隔
        idle_interval: 空闲状态检查间隔
        idle_threshold: 进入空闲状态的阈值（秒）
    """

    def __init__(
        self,
        active_interval: float = 0.5,
        idle_interval: float = 3.0,
        idle_threshold: float = 30.0,
        read_timeout: float = 0.5,
    ):
        """初始化智能剪贴板观察器
        
        Args:
            active_interval: 活跃状态检查间隔
            idle_interval: 空闲状态检查间隔
            idle_threshold: 进入空闲状态的阈值（秒）
            read_timeout: 剪贴板读取超时
        """
        super().__init__(active_interval, read_timeout)
        self.active_interval = active_interval
        self.idle_interval = idle_interval
        self.idle_threshold = idle_threshold
        self._current_interval = active_interval

    async def start(self) -> None:
        """启动智能观察"""
        self._running = True
        logger.info(
            f"智能剪贴板观察器已启动，"
            f"活跃间隔: {self.active_interval}秒，"
            f"空闲间隔: {self.idle_interval}秒"
        )
        
        try:
            while self._running:
                start_time = time.time()
                
                await self._check_once()
                
                # 计算下次检查间隔
                self._update_interval()
                
                # 计算需要等待的时间
                elapsed = time.time() - start_time
                wait_time = max(0, self._current_interval - elapsed)
                
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    
        except asyncio.CancelledError:
            logger.debug("智能剪贴板观察器已取消")
        finally:
            self._running = False
            logger.info("智能剪贴板观察器已停止")

    def _update_interval(self) -> None:
        """根据活动状态更新检查间隔"""
        now = time.time()
        time_since_last_change = now - self._last_change_time
        
        if time_since_last_change > self.idle_threshold:
            if self._current_interval != self.idle_interval:
                self._current_interval = self.idle_interval
                logger.debug(f"进入空闲状态，检查间隔调整为 {self.idle_interval}秒")
        else:
            if self._current_interval != self.active_interval:
                self._current_interval = self.active_interval
                logger.debug(f"进入活跃状态，检查间隔调整为 {self.active_interval}秒")

    def get_current_interval(self) -> float:
        """获取当前检查间隔
        
        Returns:
            当前检查间隔（秒）
        """
        return self._current_interval
