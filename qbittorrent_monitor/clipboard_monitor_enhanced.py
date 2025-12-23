"""
增强的剪贴板监控器 - 集成所有健壮性功能

特性：
- 集成统一异常处理和重试机制
- 使用增强的缓存系统
- 使用资源管理上下文管理器
- 使用统一熔断器和限流
- 集成监控和指标
- 智能错误恢复
- 自适应监控间隔
- 批量处理优化
"""

import asyncio
import logging
import time
import hashlib
from collections import deque, defaultdict
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set, Any, Callable
from dataclasses import dataclass, field

from .exceptions_enhanced import retry, get_retry_config, RetryableError
from .enhanced_cache import get_global_cache
from .resource_manager import (
    BaseAsyncResource, AsyncResourcePool, managed_resource, get_global_tracker
)
from .concurrency import (
    AsyncThrottler, AsyncBatchProcessor, get_concurrency_config,
    async_throttle
)
from .monitoring import (
    get_metrics_collector, get_health_checker, PerformanceMonitor
)
from .circuit_breaker import (
    get_global_traffic_controller, UnifiedCircuitBreaker, UnifiedRateLimiter,
    CircuitBreakerConfig, RateLimitConfig, RateLimitStrategy
)

from .config import AppConfig
from .qbittorrent_client_enhanced import EnhancedQBittorrentClient
from .ai_classifier import AIClassifier
from .notifications import NotificationManager
from .exceptions import ClipboardError
from .utils import parse_magnet, validate_magnet_link
from .clipboard_poller import ClipboardPoller, PollerConfig
from .clipboard_processor import ClipboardContentProcessor, ClipboardTask
from .clipboard_actions import ClipboardActionExecutor
from .clipboard_models import TorrentRecord

logger = logging.getLogger(__name__)


@dataclass
class MonitorStats:
    """监控统计信息"""
    total_processed: int = 0
    successful_adds: int = 0
    failed_adds: int = 0
    duplicates_skipped: int = 0
    ai_classifications: int = 0
    rule_classifications: int = 0
    url_crawls: int = 0
    batch_adds: int = 0
    clipboard_reads: int = 0
    cache_hits: int = 0
    errors: int = 0
    recovery_attempts: int = 0
    performance_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class ClipboardEvent:
    """剪贴板事件"""
    content: str
    timestamp: datetime
    event_type: str  # 'magnet', 'url', 'text'
    processed: bool = False
    error: Optional[str] = None


class EnhancedClipboardMonitor(BaseAsyncResource):
    """
    增强的剪贴板监控器

    集成所有健壮性功能的企业级监控器
    """

    def __init__(
        self,
        qbt_client: EnhancedQBittorrentClient,
        config: AppConfig
    ):
        super().__init__(f"clipboard_monitor_{id(self)}")
        self.qbt_client = qbt_client
        self.config = config

        # 初始化增强模块
        self._init_enhanced_features()

        # 基础状态
        self.last_clip = ""
        self.is_running = False
        self._is_cleaned_up = False

        # 事件队列
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._processing_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        # 初始化组件
        self.ai_classifier = AIClassifier(config.deepseek)
        self.notification_manager = NotificationManager(
            config.notifications.model_dump()
        )
        self.content_processor = ClipboardContentProcessor()
        self.action_executor = ClipboardActionExecutor(
            self.qbt_client,
            self.config,
            self.ai_classifier,
            self.notification_manager,
            self._update_stats,
            self._add_to_history,
            logger=self.logger,
        )

        # 统计信息
        self.stats = MonitorStats()
        self.processed_hashes: Set[str] = set()
        self._process_times: deque = deque(maxlen=100)

        # 轮询器配置
        base_interval = max(0.5, min(config.check_interval, 5.0))
        poller_config = PollerConfig(base_interval=base_interval)
        self.poller = ClipboardPoller(poller_config, self._on_clipboard_change)

        # 错误跟踪
        self.consecutive_errors = 0
        self.last_error_time: Optional[datetime] = None
        self.last_stats_report = datetime.now()

    def _init_enhanced_features(self):
        """初始化增强功能"""
        # 获取全局组件
        self._cache = get_global_cache()
        self._metrics = get_metrics_collector()
        self._health_checker = get_health_checker()
        self._traffic_controller = get_global_traffic_controller()
        self._tracker = get_global_tracker()
        self._performance_monitor = PerformanceMonitor(self._metrics)

        # 注册健康检查
        self._health_checker.register_check(
            f"clipboard_monitor_{self.resource_id}",
            self._check_health,
            critical=False
        )

        # 配置熔断器
        cb_config = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=5,
            timeout=120.0,
            name=f"clipboard_{self.resource_id}"
        )
        self._circuit_breaker = self._traffic_controller.add_circuit_breaker(
            f"clipboard_{self.resource_id}",
            cb_config
        )

        # 配置限流器（剪贴板事件频率通常不高）
        rl_config = RateLimitConfig(
            rate=10.0,  # 每秒10个事件
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            name=f"clipboard_{self.resource_id}"
        )
        self._rate_limiter = self._traffic_controller.add_rate_limiter(
            f"clipboard_{self.resource_id}",
            rl_config
        )

        # 配置节流器
        concurrency_config = get_concurrency_config("low")
        self._throttler = AsyncThrottler(concurrency_config['max_concurrent'])

        # 配置批处理器（处理批量剪贴板事件）
        self._batch_processor = AsyncBatchProcessor(
            batch_size=5,
            max_wait_time=0.5,
            max_workers=2
        )

    async def _do_close(self):
        """关闭资源"""
        self.is_running = False
        self.poller.stop()

        # 清理AI分类器
        if hasattr(self.ai_classifier, 'cleanup'):
            await self.ai_classifier.cleanup()

        logger.info(f"ClipboardMonitor已关闭: {self.resource_id}")

    async def _check_health(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            return {
                "status": "healthy",
                "message": f"Running: {self.is_running}, "
                          f"Processed: {self.stats.total_processed}, "
                          f"Errors: {self.stats.errors}",
                "stats": {
                    "total_processed": self.stats.total_processed,
                    "successful_adds": self.stats.successful_adds,
                    "failed_adds": self.stats.failed_adds,
                    "duplicates_skipped": self.stats.duplicates_skipped,
                    "errors": self.stats.errors
                }
            }
        except Exception as e:
            return {
                "status": "critical",
                "message": f"Health check failed: {str(e)}"
            }

    def _update_stats(self, key: str, value: int = 1):
        """更新统计信息"""
        if hasattr(self.stats, key):
            current_value = getattr(self.stats, key)
            setattr(self.stats, key, current_value + value)

    def _add_to_history(self, record: TorrentRecord):
        """添加到历史记录"""
        # 这里可以添加到数据库或文件
        # 暂时只是记录日志
        self.logger.debug(f"添加历史记录: {record.title}")

    async def start(self):
        """启动剪贴板监控"""
        self.is_running = True
        self.logger.info("开始监控剪贴板...")

        # 启动轮询器
        poller_task = asyncio.create_task(self.poller.start())

        # 启动处理任务
        processor_task = asyncio.create_task(self._process_events())

        try:
            # 主监控循环
            while self.is_running:
                await asyncio.sleep(0.1)  # 短暂休眠

                # 定期维护
                await self._periodic_maintenance()

        except asyncio.CancelledError:
            self.logger.info("监控已取消")
            raise
        except Exception as e:
            self.logger.error(f"监控异常: {str(e)}")
            await self._handle_monitor_error(e)
            raise
        finally:
            self.is_running = False
            self.poller.stop()
            poller_task.cancel()
            processor_task.cancel()

            try:
                await asyncio.gather(poller_task, processor_task, return_exceptions=True)
            except asyncio.CancelledError:
                pass

            await self.cleanup()
            self.logger.info("剪贴板监控已停止")

    def stop(self):
        """停止监控"""
        self.is_running = False
        self.poller.stop()

    def _on_clipboard_change(self, text: str):
        """处理剪贴板变更回调"""
        if not self.is_running:
            return

        self.stats.clipboard_reads = self.poller.clipboard_reads

        # 限流控制
        if not self._rate_limiter.available_tokens() >= 1.0:
            self.logger.debug("跳过事件（限流）")
            return

        # 添加到事件队列
        try:
            self._event_queue.put_nowait(ClipboardEvent(
                content=text or "",
                timestamp=datetime.now(),
                event_type=self._determine_event_type(text or "")
            ))
        except asyncio.QueueFull:
            self.logger.warning("事件队列已满，丢弃事件")

    def _determine_event_type(self, text: str) -> str:
        """确定事件类型"""
        if not text:
            return 'text'

        if validate_magnet_link(text):
            return 'magnet'

        if text.startswith(('http://', 'https://')):
            return 'url'

        return 'text'

    async def _process_events(self):
        """处理事件队列"""
        while self.is_running:
            try:
                # 获取事件
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )

                # 添加到处理队列
                await self._processing_queue.put(event)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"处理事件时出错: {str(e)}")
                await asyncio.sleep(0.1)

        # 处理剩余事件
        while not self._processing_queue.empty():
            try:
                event = self._processing_queue.get_nowait()
                await self._process_single_event(event)
            except asyncio.QueueEmpty:
                break

    async def _process_single_event(self, event: ClipboardEvent):
        """处理单个事件"""
        start_time = time.time()

        try:
            # 检查是否重复
            if await self._is_duplicate(event.content):
                self.stats.duplicates_skipped += 1
                return

            # 处理事件
            if event.event_type == "magnet":
                await self._handle_magnet_event(event)
            elif event.event_type == "url":
                await self._handle_url_event(event)
            else:
                await self._handle_text_event(event)

            # 记录成功
            self.stats.total_processed += 1
            self.consecutive_errors = 0
            self.last_error_time = None

            # 记录性能指标
            process_time = (time.time() - start_time) * 1000
            await self._performance_monitor.track_request(
                endpoint="process_event",
                duration_ms=process_time,
                success=True
            )

        except Exception as e:
            self.stats.errors += 1
            self.consecutive_errors += 1
            self.last_error_time = datetime.now()

            self.logger.error(f"处理事件失败: {str(e)}")

            # 错误恢复
            await self._handle_event_error(event, e)

    async def _handle_magnet_event(self, event: ClipboardEvent):
        """处理磁力链接事件"""
        async with async_throttle(self._throttler, "magnet_processing"):
            # 使用流量控制器调用
            await self._traffic_controller.call(
                self.action_executor.handle_magnet,
                event.content,
                circuit_breaker_name=f"clipboard_{self.resource_id}",
                rate_limiter_name=f"clipboard_{self.resource_id}",
            )

            self.stats.successful_adds += 1

            # 记录指标
            await self._metrics.record_counter(
                "clipboard.magnet_processed",
                1.0
            )

    async def _handle_url_event(self, event: ClipboardEvent):
        """处理URL事件"""
        async with async_throttle(self._throttler, "url_processing"):
            await self.action_executor.handle_url(event.content)
            self.stats.url_crawls += 1

            # 记录指标
            await self._metrics.record_counter(
                "clipboard.url_processed",
                1.0
            )

    async def _handle_text_event(self, event: ClipboardEvent):
        """处理文本事件"""
        # 文本事件通常不需要特殊处理
        pass

    async def _is_duplicate(self, content: str) -> bool:
        """检查是否重复"""
        # 生成内容哈希
        content_hash = hashlib.md5(content.encode()).hexdigest()

        # 检查缓存
        cache_key = f"clipboard:event:{content_hash}"
        cached = await self._cache.get(cache_key)
        if cached:
            self.stats.cache_hits += 1
            return True

        # 缓存24小时
        await self._cache.set(cache_key, True, ttl=86400)
        return False

    async def _handle_event_error(self, event: ClipboardEvent, error: Exception):
        """处理事件错误"""
        self.stats.errors += 1

        # 记录指标
        await self._metrics.record_counter(
            "clipboard.event_error",
            1.0
        )

        # 错误恢复策略
        if self.consecutive_errors >= 5:
            self.logger.error("连续错误过多，尝试恢复...")
            self.stats.recovery_attempts += 1

            # 清理缓存
            await self._cache.clear()
            self.consecutive_errors = 0

            # 重新初始化组件
            await self._recover_from_error()

    async def _recover_from_error(self):
        """从错误中恢复"""
        try:
            # 重新初始化关键组件
            if hasattr(self.ai_classifier, 'cleanup'):
                await self.ai_classifier.cleanup()

            # 重新创建分类器
            self.ai_classifier = AIClassifier(self.config.deepseek)

            self.logger.info("组件恢复完成")
        except Exception as e:
            self.logger.error(f"恢复失败: {str(e)}")

    async def _periodic_maintenance(self):
        """定期维护"""
        now = datetime.now()

        # 每30秒报告一次统计
        if now - self.last_stats_report >= timedelta(seconds=30):
            await self._report_stats()
            self.last_stats_report = now

        # 清理过期缓存（每小时）
        if now.hour != self._cache_cleanup_hour:
            await self._cleanup_cache()
            self._cache_cleanup_hour = now.hour

    async def _report_stats(self):
        """报告统计信息"""
        self.logger.info(
            f"剪贴板监控统计: "
            f"处理={self.stats.total_processed}, "
            f"成功={self.stats.successful_adds}, "
            f"失败={self.stats.failed_adds}, "
            f"跳过={self.stats.duplicates_skipped}, "
            f"错误={self.stats.errors}"
        )

    async def _cleanup_cache(self):
        """清理缓存"""
        # 清理旧的事件缓存
        # 实际实现中可以从缓存中移除过期条目
        pass

    async def _handle_monitor_error(self, error: Exception):
        """处理监控错误"""
        self.logger.error(f"监控器错误: {str(error)}")

        # 记录指标
        await self._metrics.record_counter(
            "clipboard.monitor_error",
            1.0
        )

        # 如果连续错误过多，尝试重启
        if self.consecutive_errors >= 10:
            self.logger.critical("连续错误过多，停止监控")
            self.stop()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        circuit_stats = self._circuit_breaker.get_stats()
        rate_limiter_stats = self._rate_limiter.get_stats()

        return {
            "resource_id": self.resource_id,
            "is_running": self.is_running,
            "stats": {
                "total_processed": self.stats.total_processed,
                "successful_adds": self.stats.successful_adds,
                "failed_adds": self.stats.failed_adds,
                "duplicates_skipped": self.stats.duplicates_skipped,
                "ai_classifications": self.stats.ai_classifications,
                "rule_classifications": self.stats.rule_classifications,
                "url_crawls": self.stats.url_crawls,
                "batch_adds": self.stats.batch_adds,
                "clipboard_reads": self.stats.clipboard_reads,
                "cache_hits": self.stats.cache_hits,
                "errors": self.stats.errors,
                "recovery_attempts": self.stats.recovery_attempts
            },
            "circuit_breaker": circuit_stats,
            "rate_limiter": rate_limiter_stats,
            "throttler": {
                "active_tasks": self._throttler.get_stats().active_tasks,
                "queue_size": self._throttler.get_stats().queue_size
            },
            "processed_hashes": len(self.processed_hashes),
            "consecutive_errors": self.consecutive_errors,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None
        }

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """异步上下文管理器退出"""
        await self.close()
        return False
