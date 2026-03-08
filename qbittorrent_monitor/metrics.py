"""Prometheus 指标导出模块

提供 qbittorrent-clipboard-monitor 的 Prometheus 指标导出功能。
支持 Counter、Gauge、Histogram 等多种指标类型。
"""

import time
import logging
from typing import Optional, Callable, Any
from contextlib import contextmanager

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

logger = logging.getLogger(__name__)

# 全局注册表
REGISTRY = CollectorRegistry()

# 指标前缀
METRIC_PREFIX = "qbmonitor"


class MetricsCollector:
    """Prometheus 指标收集器
    
    收集和导出 qbittorrent-clipboard-monitor 的各项指标。
    """
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """初始化指标收集器
        
        Args:
            registry: Prometheus 注册表，默认使用全局注册表
        """
        self.registry = registry or REGISTRY
        self._enabled = True
        
        # 初始化 Counter 指标
        self._init_counters()
        
        # 初始化 Gauge 指标
        self._init_gauges()
        
        # 初始化 Histogram 指标
        self._init_histograms()
        
        logger.debug("MetricsCollector 初始化完成")
    
    def _init_counters(self) -> None:
        """初始化 Counter 指标"""
        # 处理的磁力链接总数
        self.torrents_processed_total = Counter(
            f"{METRIC_PREFIX}_torrents_processed_total",
            "Total number of torrents processed",
            ["category"],  # 按分类标签
            registry=self.registry,
        )
        
        # 成功添加的种子数
        self.torrents_added_success_total = Counter(
            f"{METRIC_PREFIX}_torrents_added_success_total",
            "Total number of torrents successfully added to qBittorrent",
            ["category"],
            registry=self.registry,
        )
        
        # 添加失败的种子数
        self.torrents_added_failed_total = Counter(
            f"{METRIC_PREFIX}_torrents_added_failed_total",
            "Total number of failed torrent additions",
            ["category", "reason"],  # 按分类和失败原因标签
            registry=self.registry,
        )
        
        # 跳过的重复种子数
        self.duplicates_skipped_total = Counter(
            f"{METRIC_PREFIX}_duplicates_skipped_total",
            "Total number of duplicate torrents skipped",
            ["reason"],  # 原因: duplicate, debounce, invalid
            registry=self.registry,
        )
        
        # 剪贴板内容变化次数
        self.clipboard_changes_total = Counter(
            f"{METRIC_PREFIX}_clipboard_changes_total",
            "Total number of clipboard content changes detected",
            registry=self.registry,
        )
        
        # API 调用次数
        self.api_calls_total = Counter(
            f"{METRIC_PREFIX}_api_calls_total",
            "Total number of qBittorrent API calls",
            ["endpoint", "status"],  # 端点和状态
            registry=self.registry,
        )
        
        # 分类方法统计
        self.classifications_total = Counter(
            f"{METRIC_PREFIX}_classifications_total",
            "Total number of content classifications",
            ["method", "category"],  # 方法: rule, ai, fallback
            registry=self.registry,
        )
    
    def _init_gauges(self) -> None:
        """初始化 Gauge 指标"""
        # 监控器运行状态 (1=running, 0=stopped)
        self.monitor_running = Gauge(
            f"{METRIC_PREFIX}_monitor_running",
            "Whether the clipboard monitor is running (1=running, 0=stopped)",
            registry=self.registry,
        )
        
        # 剪贴板检查间隔
        self.clipboard_check_interval_seconds = Gauge(
            f"{METRIC_PREFIX}_clipboard_check_interval_seconds",
            "Current clipboard check interval in seconds",
            registry=self.registry,
        )
        
        # 缓存大小
        self.cache_size = Gauge(
            f"{METRIC_PREFIX}_cache_size",
            "Current number of items in cache",
            ["cache_type"],  # clipboard, classification
            registry=self.registry,
        )
        
        # 缓存命中率
        self.cache_hit_rate = Gauge(
            f"{METRIC_PREFIX}_cache_hit_rate",
            "Cache hit rate (0.0-1.0)",
            ["cache_type"],
            registry=self.registry,
        )
        
        # 队列中待处理的磁力链接数
        self.pending_magnets = Gauge(
            f"{METRIC_PREFIX}_pending_magnets",
            "Number of magnets pending in debounce queue",
            registry=self.registry,
        )
        
        # 已处理的磁力链接集合大小
        self.processed_magnets_count = Gauge(
            f"{METRIC_PREFIX}_processed_magnets_count",
            "Number of unique magnets processed",
            registry=self.registry,
        )
        
        # AI 客户端可用状态
        self.ai_client_available = Gauge(
            f"{METRIC_PREFIX}_ai_client_available",
            "Whether AI client is available (1=available, 0=unavailable)",
            registry=self.registry,
        )
        
        # qBittorrent 连接状态
        self.qbittorrent_connected = Gauge(
            f"{METRIC_PREFIX}_qbittorrent_connected",
            "Whether connected to qBittorrent (1=connected, 0=disconnected)",
            registry=self.registry,
        )
    
    def _init_histograms(self) -> None:
        """初始化 Histogram 指标"""
        # 剪贴板检查耗时
        self.clipboard_check_duration_seconds = Histogram(
            f"{METRIC_PREFIX}_clipboard_check_duration_seconds",
            "Time spent checking clipboard in seconds",
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry,
        )
        
        # 种子添加耗时
        self.torrent_add_duration_seconds = Histogram(
            f"{METRIC_PREFIX}_torrent_add_duration_seconds",
            "Time spent adding a torrent to qBittorrent in seconds",
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry,
        )
        
        # 分类耗时
        self.classify_duration_seconds = Histogram(
            f"{METRIC_PREFIX}_classify_duration_seconds",
            "Time spent classifying content in seconds",
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
            registry=self.registry,
        )
        
        # API 调用耗时
        self.api_call_duration_seconds = Histogram(
            f"{METRIC_PREFIX}_api_call_duration_seconds",
            "Time spent on qBittorrent API calls in seconds",
            ["endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=self.registry,
        )
    
    @property
    def enabled(self) -> bool:
        """指标收集是否启用"""
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool) -> None:
        """设置指标收集启用状态"""
        self._enabled = value
        logger.info(f"指标收集已{'启用' if value else '禁用'}")
    
    def generate_latest(self) -> bytes:
        """生成最新的指标数据
        
        Returns:
            Prometheus 格式的指标数据
        """
        return generate_latest(self.registry)
    
    def content_type(self) -> str:
        """获取指标内容的 MIME 类型
        
        Returns:
            CONTENT_TYPE_LATEST
        """
        return CONTENT_TYPE_LATEST


# 全局指标收集器实例
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> Optional[MetricsCollector]:
    """获取全局指标收集器实例
    
    Returns:
        MetricsCollector 实例，如果未初始化则返回 None
    """
    return _metrics_collector


def init_metrics(enabled: bool = True) -> Optional[MetricsCollector]:
    """初始化全局指标收集器
    
    Args:
        enabled: 是否启用指标收集
        
    Returns:
        MetricsCollector 实例
    """
    global _metrics_collector
    
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
        _metrics_collector.enabled = enabled
        logger.info(f"Prometheus 指标收集器已初始化 (enabled={enabled})")
    
    return _metrics_collector


def record_torrent_processed(category: str = "unknown") -> None:
    """记录处理的磁力链接
    
    Args:
        category: 分类名称
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.torrents_processed_total.labels(category=category).inc()


def record_torrent_added_success(category: str = "unknown") -> None:
    """记录成功添加的种子
    
    Args:
        category: 分类名称
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.torrents_added_success_total.labels(category=category).inc()


def record_torrent_added_failed(category: str = "unknown", reason: str = "unknown") -> None:
    """记录添加失败的种子
    
    Args:
        category: 分类名称
        reason: 失败原因
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.torrents_added_failed_total.labels(
            category=category, reason=reason
        ).inc()


def record_duplicate_skipped(reason: str = "duplicate") -> None:
    """记录跳过的重复种子
    
    Args:
        reason: 跳过原因 (duplicate, debounce, invalid)
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.duplicates_skipped_total.labels(reason=reason).inc()


def record_clipboard_change() -> None:
    """记录剪贴板内容变化"""
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.clipboard_changes_total.inc()


def record_api_call(endpoint: str, status: str = "success") -> None:
    """记录 API 调用
    
    Args:
        endpoint: API 端点
        status: 调用状态 (success, error, timeout)
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.api_calls_total.labels(endpoint=endpoint, status=status).inc()


def record_classification(method: str, category: str) -> None:
    """记录分类操作
    
    Args:
        method: 分类方法 (rule, ai, fallback)
        category: 分类结果
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.classifications_total.labels(method=method, category=category).inc()


def set_monitor_running(running: bool) -> None:
    """设置监控器运行状态
    
    Args:
        running: 是否运行中
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.monitor_running.set(1.0 if running else 0.0)


def set_clipboard_check_interval(interval: float) -> None:
    """设置剪贴板检查间隔
    
    Args:
        interval: 检查间隔（秒）
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.clipboard_check_interval_seconds.set(interval)


def set_cache_size(cache_type: str, size: int) -> None:
    """设置缓存大小
    
    Args:
        cache_type: 缓存类型 (clipboard, classification)
        size: 缓存项数量
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.cache_size.labels(cache_type=cache_type).set(size)


def set_cache_hit_rate(cache_type: str, hit_rate: float) -> None:
    """设置缓存命中率
    
    Args:
        cache_type: 缓存类型
        hit_rate: 命中率 (0.0-1.0)
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.cache_hit_rate.labels(cache_type=cache_type).set(hit_rate)


def set_pending_magnets(count: int) -> None:
    """设置待处理的磁力链接数量
    
    Args:
        count: 待处理数量
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.pending_magnets.set(count)


def set_processed_magnets_count(count: int) -> None:
    """设置已处理的磁力链接数量
    
    Args:
        count: 已处理数量
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.processed_magnets_count.set(count)


def set_ai_client_available(available: bool) -> None:
    """设置 AI 客户端可用状态
    
    Args:
        available: 是否可用
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.ai_client_available.set(1.0 if available else 0.0)


def set_qbittorrent_connected(connected: bool) -> None:
    """设置 qBittorrent 连接状态
    
    Args:
        connected: 是否已连接
    """
    collector = get_metrics_collector()
    if collector and collector.enabled:
        collector.qbittorrent_connected.set(1.0 if connected else 0.0)


@contextmanager
def timed_clipboard_check():
    """剪贴板检查耗时上下文管理器"""
    collector = get_metrics_collector()
    if not collector or not collector.enabled:
        yield
        return
    
    start = time.time()
    try:
        yield
    finally:
        collector.clipboard_check_duration_seconds.observe(time.time() - start)


@contextmanager
def timed_torrent_add():
    """种子添加耗时上下文管理器"""
    collector = get_metrics_collector()
    if not collector or not collector.enabled:
        yield
        return
    
    start = time.time()
    try:
        yield
    finally:
        collector.torrent_add_duration_seconds.observe(time.time() - start)


@contextmanager
def timed_classification():
    """分类耗时上下文管理器"""
    collector = get_metrics_collector()
    if not collector or not collector.enabled:
        yield
        return
    
    start = time.time()
    try:
        yield
    finally:
        collector.classify_duration_seconds.observe(time.time() - start)


@contextmanager
def timed_api_call(endpoint: str):
    """API 调用耗时上下文管理器
    
    Args:
        endpoint: API 端点名称
    """
    collector = get_metrics_collector()
    if not collector or not collector.enabled:
        yield
        return
    
    start = time.time()
    try:
        yield
    finally:
        collector.api_call_duration_seconds.labels(endpoint=endpoint).observe(
            time.time() - start
        )


def create_timer_decorator(timer_func: Callable[[], Any]) -> Callable:
    """创建计时装饰器工厂函数
    
    Args:
        timer_func: 返回上下文管理器的函数
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            with timer_func():
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            with timer_func():
                return func(*args, **kwargs)
        
        import asyncio
        import inspect
        if inspect.iscoroutinefunction(func):
            async_wrapper.__name__ = func.__name__
            async_wrapper.__doc__ = func.__doc__
            return async_wrapper
        else:
            sync_wrapper.__name__ = func.__name__
            sync_wrapper.__doc__ = func.__doc__
            return sync_wrapper
    
    return decorator
