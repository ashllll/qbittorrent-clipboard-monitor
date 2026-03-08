"""异步剪贴板读取模块 - 使用后台线程和队列"""
import asyncio
import threading
import time
import logging
from queue import Queue, Empty
from typing import Optional, AsyncGenerator

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False

logger = logging.getLogger(__name__)


class AsyncClipboardReader:
    """高性能异步剪贴板读取器
    
    使用后台线程持续监控，通过队列异步传递变化
    相比线程池方案，减少线程切换开销
    """
    
    def __init__(self, poll_interval: float = 0.1, max_queue_size: int = 10):
        """
        Args:
            poll_interval: 轮询间隔（秒）
            max_queue_size: 队列最大长度
        """
        self._poll_interval = poll_interval
        self._max_queue_size = max_queue_size
        self._queue: Queue[Optional[str]] = Queue(maxsize=max_queue_size)
        self._last_content: Optional[str] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
    def start(self) -> None:
        """启动后台监控线程"""
        if not PYPERCLIP_AVAILABLE:
            raise RuntimeError("pyperclip not available")
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.debug(f"剪贴板监控线程已启动 (interval={self._poll_interval}s)")
        
    def stop(self) -> None:
        """停止监控"""
        self._running = False
        
        # 发送停止信号
        try:
            self._queue.put_nowait(None)
        except:
            pass
        
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        
        logger.debug("剪贴板监控线程已停止")
    
    def _monitor_loop(self) -> None:
        """后台监控循环"""
        while self._running:
            try:
                current = pyperclip.paste()
                
                # 检查内容是否变化
                if current != self._last_content:
                    self._last_content = current
                    
                    # 非阻塞放入队列（如果满了，丢弃旧值）
                    if self._queue.full():
                        try:
                            self._queue.get_nowait()  # 丢弃旧值
                        except Empty:
                            pass
                    
                    try:
                        self._queue.put_nowait(current)
                    except:
                        pass
                        
            except Exception as e:
                logger.debug(f"剪贴板读取异常: {e}")
            
            time.sleep(self._poll_interval)
    
    async def get_clipboard(self, timeout: Optional[float] = None) -> Optional[str]:
        """异步获取剪贴板内容
        
        仅在内容变化时返回，减少无效处理
        
        Args:
            timeout: 超时时间（秒），None 表示无限等待
            
        Returns:
            剪贴板内容，超时返回 None
        """
        loop = asyncio.get_event_loop()
        
        try:
            # 使用队列获取，避免线程切换开销
            content = await asyncio.wait_for(
                loop.run_in_executor(None, self._queue.get),
                timeout=timeout
            )
            return content
        except asyncio.TimeoutError:
            return None
    
    async def changes(self) -> AsyncGenerator[str, None]:
        """异步迭代器，仅在剪贴板变化时产生值"""
        while self._running:
            content = await self.get_clipboard(timeout=1.0)
            if content is not None:
                yield content


class SmartClipboardMonitor:
    """智能剪贴板监控器 - 自适应轮询频率"""
    
    def __init__(self, min_interval: float = 0.1, max_interval: float = 5.0):
        """
        Args:
            min_interval: 最小轮询间隔（活跃状态）
            max_interval: 最大轮询间隔（空闲状态）
        """
        self._reader = AsyncClipboardReader(poll_interval=min_interval)
        self._min_interval = min_interval
        self._max_interval = max_interval
        self._adaptive_interval = min_interval
        self._activity_window: deque = deque(maxlen=10)
        
    async def monitor(self) -> AsyncGenerator[str, None]:
        """智能监控循环
        
        根据用户活跃度自适应调整轮询频率
        """
        self._reader.start()
        try:
            async for content in self._reader.changes():
                # 记录活动
                self._activity_window.append(time.time())
                
                # 自适应调整轮询间隔
                self._adaptive_interval = self._calculate_interval()
                self._reader._poll_interval = self._adaptive_interval
                
                yield content
        finally:
            self._reader.stop()
    
    def _calculate_interval(self) -> float:
        """根据活动频率计算最佳轮询间隔"""
        if len(self._activity_window) < 2:
            return self._max_interval
        
        # 计算最近活动的平均间隔
        intervals = [
            self._activity_window[i] - self._activity_window[i-1]
            for i in range(1, len(self._activity_window))
        ]
        avg_interval = sum(intervals) / len(intervals)
        
        # 根据活跃度调整
        if avg_interval < 0.5:  # 高频活动
            return self._min_interval
        elif avg_interval < 2.0:  # 中等活动
            return (self._min_interval + self._max_interval) / 4
        else:  # 低频活动
            return min(avg_interval / 2, self._max_interval)
    
    def get_stats(self) -> dict:
        """获取监控统计"""
        return {
            "current_interval": self._adaptive_interval,
            "activity_count": len(self._activity_window),
            "min_interval": self._min_interval,
            "max_interval": self._max_interval,
        }


class DebouncedClipboardReader:
    """防抖剪贴板读取器 - 防止短时间内多次触发"""
    
    def __init__(self, debounce_seconds: float = 0.5, **kwargs):
        """
        Args:
            debounce_seconds: 防抖时间窗口
            **kwargs: 传递给 AsyncClipboardReader 的参数
        """
        self._reader = AsyncClipboardReader(**kwargs)
        self._debounce_seconds = debounce_seconds
        self._last_content: Optional[str] = None
        self._last_time: float = 0
        
    def start(self) -> None:
        self._reader.start()
        
    def stop(self) -> None:
        self._reader.stop()
    
    async def changes(self) -> AsyncGenerator[str, None]:
        """防抖后的剪贴板变化"""
        async for content in self._reader.changes():
            now = time.time()
            
            # 防抖检查
            if (content == self._last_content and 
                now - self._last_time < self._debounce_seconds):
                continue
            
            self._last_content = content
            self._last_time = now
            yield content
