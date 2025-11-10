"""
监控指标和健康检查模块

提供全面的系统监控、性能指标收集和健康状态检查
"""

import asyncio
import time
import psutil
import logging
from typing import Any, Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
import json

from .enhanced_cache import get_global_cache, get_global_memory_monitor
from .concurrency import get_concurrency_config
from .resource_manager import get_global_tracker, get_resource_health_report

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class MetricType(Enum):
    """指标类型枚举"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class Metric:
    """指标数据"""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "value": self.value,
            "type": self.metric_type.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
            "unit": self.unit,
            "description": self.description
        }


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    critical: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "details": self.details,
            "critical": self.critical
        }


class MetricsCollector:
    """指标收集器"""

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._metrics: deque = deque(maxlen=max_size)
        self._metric_aggregators: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = asyncio.Lock()

        # 预定义的核心指标
        self._core_metrics = {
            "app_start_time": time.time(),
            "total_requests": 0,
            "failed_requests": 0,
            "active_connections": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }

    async def record_metric(self, metric: Metric) -> None:
        """记录指标"""
        async with self._lock:
            self._metrics.append(metric)

            # 触发聚合器
            for aggregator in self._metric_aggregators.get(metric.name, []):
                try:
                    aggregator(metric)
                except Exception as e:
                    logger.error(f"指标聚合器执行失败: {str(e)}")

    async def record_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> None:
        """记录计数器指标"""
        metric = Metric(
            name=name,
            value=value,
            metric_type=MetricType.COUNTER,
            timestamp=datetime.now(),
            labels=labels or {},
            **kwargs
        )
        await self.record_metric(metric)

    async def record_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> None:
        """记录仪表盘指标"""
        metric = Metric(
            name=name,
            value=value,
            metric_type=MetricType.GAUGE,
            timestamp=datetime.now(),
            labels=labels or {},
            **kwargs
        )
        await self.record_metric(metric)

    async def record_timer(
        self,
        name: str,
        duration_ms: float,
        labels: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> None:
        """记录定时器指标"""
        metric = Metric(
            name=name,
            value=duration_ms,
            metric_type=MetricType.TIMER,
            timestamp=datetime.now(),
            labels=labels or {},
            **kwargs
        )
        await self.record_metric(metric)

    def add_aggregator(self, metric_name: str, aggregator: Callable) -> None:
        """添加指标聚合器"""
        self._metric_aggregators[metric_name].append(aggregator)

    async def get_metrics(
        self,
        name: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Metric]:
        """获取指标"""
        async with self._lock:
            metrics = list(self._metrics)

        # 过滤
        if name:
            metrics = [m for m in metrics if m.name == name]

        if since:
            metrics = [m for m in metrics if m.timestamp >= since]

        # 限制数量
        return metrics[-limit:]

    async def get_aggregated_metrics(self, window: timedelta) -> Dict[str, Any]:
        """获取聚合指标"""
        now = datetime.now()
        window_start = now - window

        metrics = await self.get_metrics(since=window_start)

        aggregated = defaultdict(list)
        for metric in metrics:
            aggregated[metric.name].append(metric.value)

        result = {}
        for name, values in aggregated.items():
            result[name] = {
                "count": len(values),
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "avg": sum(values) / len(values) if values else 0,
                "latest": values[-1] if values else 0
            }

        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取收集器统计"""
        return {
            "total_metrics": len(self._metrics),
            "max_size": self.max_size,
            "core_metrics": self._core_metrics.copy()
        }


class HealthChecker:
    """健康检查器"""

    def __init__(self):
        self.checks: Dict[str, Callable] = {}
        self.last_results: Dict[str, HealthCheckResult] = {}
        self._lock = asyncio.Lock()

    def register_check(
        self,
        name: str,
        check_func: Callable,
        critical: bool = False
    ) -> None:
        """注册健康检查"""
        self.checks[name] = check_func
        if critical:
            logger.info(f"注册关键健康检查: {name}")

    async def run_check(self, name: str) -> HealthCheckResult:
        """运行单个健康检查"""
        if name not in self.checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"未找到健康检查: {name}",
                timestamp=datetime.now(),
                duration_ms=0,
                critical=False
            )

        start_time = time.time()
        check_func = self.checks[name]

        try:
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func()
            else:
                result = check_func()

            duration_ms = (time.time() - start_time) * 1000

            # 确保返回的是HealthCheckResult
            if not isinstance(result, HealthCheckResult):
                result = HealthCheckResult(
                    name=name,
                    status=HealthStatus.HEALTHY,
                    message=str(result),
                    timestamp=datetime.now(),
                    duration_ms=duration_ms
                )
            else:
                result.duration_ms = duration_ms
                result.timestamp = datetime.now()

            async with self._lock:
                self.last_results[name] = result

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.CRITICAL,
                message=f"健康检查失败: {str(e)}",
                timestamp=datetime.now(),
                duration_ms=duration_ms,
                critical=True
            )

            async with self._lock:
                self.last_results[name] = result

            logger.error(f"健康检查 {name} 执行失败: {str(e)}")
            return result

    async def run_all_checks(self) -> List[HealthCheckResult]:
        """运行所有健康检查"""
        results = []
        for name in self.checks.keys():
            result = await self.run_check(name)
            results.append(result)

        return results

    async def get_overall_status(self) -> HealthStatus:
        """获取整体健康状态"""
        results = list(self.last_results.values())

        if not results:
            return HealthStatus.UNKNOWN

        # 如果有关键检查失败，返回CRITICAL
        for result in results:
            if result.critical and result.status == HealthStatus.CRITICAL:
                return HealthStatus.CRITICAL

        # 如果有检查失败，返回WARNING
        for result in results:
            if result.status == HealthStatus.CRITICAL:
                return HealthStatus.CRITICAL

        # 如果有检查警告，返回WARNING
        for result in results:
            if result.status == HealthStatus.WARNING:
                return HealthStatus.WARNING

        return HealthStatus.HEALTHY

    def get_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        overall_status = asyncio.create_task(self.get_overall_status())
        results = [r.to_dict() for r in self.last_results.values()]

        return {
            "overall_status": overall_status,
            "checks": results,
            "check_count": len(self.checks),
            "last_check": max(
                (r.timestamp for r in self.last_results.values()),
                default=None
            ).isoformat() if self.last_results else None
        }


class SystemMonitor:
    """系统监控器"""

    def __init__(self, check_interval: float = 10.0):
        self.check_interval = check_interval
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._metrics_collector: Optional[MetricsCollector] = None

    async def start(self, metrics_collector: MetricsCollector) -> None:
        """启动系统监控"""
        if self._is_running:
            return

        self._is_running = True
        self._metrics_collector = metrics_collector
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"系统监控已启动 (检查间隔: {self.check_interval}s)")

    async def stop(self) -> None:
        """停止系统监控"""
        self._is_running = False
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("系统监控已停止")

    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._is_running:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"系统监控循环错误: {str(e)}")
                await asyncio.sleep(self.check_interval)

    async def _collect_system_metrics(self) -> None:
        """收集系统指标"""
        if not self._metrics_collector:
            return

        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=0.1)
            await self._metrics_collector.record_gauge(
                "system.cpu.usage_percent",
                cpu_percent,
                unit="%",
                description="CPU使用率"
            )

            # 内存使用情况
            memory = psutil.virtual_memory()
            await self._metrics_collector.record_gauge(
                "system.memory.total_bytes",
                memory.total,
                unit="bytes",
                description="系统总内存"
            )
            await self._metrics_collector.record_gauge(
                "system.memory.used_bytes",
                memory.used,
                unit="bytes",
                description="已使用内存"
            )
            await self._metrics_collector.record_gauge(
                "system.memory.available_bytes",
                memory.available,
                unit="bytes",
                description="可用内存"
            )
            await self._metrics_collector.record_gauge(
                "system.memory.usage_percent",
                memory.percent,
                unit="%",
                description="内存使用率"
            )

            # 磁盘使用情况
            disk = psutil.disk_usage('/')
            await self._metrics_collector.record_gauge(
                "system.disk.total_bytes",
                disk.total,
                unit="bytes",
                description="磁盘总容量"
            )
            await self._metrics_collector.record_gauge(
                "system.disk.used_bytes",
                disk.used,
                unit="bytes",
                description="已使用磁盘空间"
            )
            await self._metrics_collector.record_gauge(
                "system.disk.free_bytes",
                disk.free,
                unit="bytes",
                description="可用磁盘空间"
            )
            await self._metrics_collector.record_gauge(
                "system.disk.usage_percent",
                (disk.used / disk.total) * 100,
                unit="%",
                description="磁盘使用率"
            )

            # 网络IO
            net_io = psutil.net_io_counters()
            if net_io:
                await self._metrics_collector.record_gauge(
                    "system.network.bytes_sent",
                    net_io.bytes_sent,
                    unit="bytes",
                    description="网络发送字节数"
                )
                await self._metrics_collector.record_gauge(
                    "system.network.bytes_recv",
                    net_io.bytes_recv,
                    unit="bytes",
                    description="网络接收字节数"
                )

        except Exception as e:
            logger.error(f"收集系统指标失败: {str(e)}")


class AlertManager:
    """警报管理器"""

    def __init__(self):
        self.alerts: deque = deque(maxlen=1000)
        self.handlers: List[Callable] = []
        self._lock = asyncio.Lock()

    def add_handler(self, handler: Callable) -> None:
        """添加警报处理器"""
        self.handlers.append(handler)

    async def send_alert(
        self,
        level: str,
        message: str,
        source: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """发送警报"""
        alert = {
            "level": level,
            "message": message,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }

        async with self._lock:
            self.alerts.append(alert)

        # 触发处理器
        for handler in self.handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"警报处理器执行失败: {str(e)}")

        # 记录日志
        if level == "CRITICAL":
            logger.critical(f"[ALERT] {source}: {message}")
        elif level == "WARNING":
            logger.warning(f"[ALERT] {source}: {message}")
        else:
            logger.info(f"[ALERT] {source}: {message}")

    async def get_recent_alerts(
        self,
        level: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取最近警报"""
        alerts = list(self.alerts)

        if level:
            alerts = [a for a in alerts if a["level"] == level]

        return alerts[-limit:]


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.request_times: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )

    async def track_request(
        self,
        endpoint: str,
        duration_ms: float,
        success: bool,
        status_code: Optional[int] = None
    ) -> None:
        """跟踪请求性能"""
        # 记录定时器指标
        await self.metrics_collector.record_timer(
            f"http.request.duration",
            duration_ms,
            labels={
                "endpoint": endpoint,
                "status": "success" if success else "error"
            },
            unit="ms"
        )

        # 记录计数器
        await self.metrics_collector.record_counter(
            "http.request.count",
            1.0,
            labels={
                "endpoint": endpoint,
                "status": "success" if success else "error"
            }
        )

        # 记录状态码
        if status_code:
            await self.metrics_collector.record_counter(
                "http.response.status_code",
                1.0,
                labels={"status_code": str(status_code)}
            )

        # 保存请求时间
        self.request_times[endpoint].append(duration_ms)

    async def get_endpoint_stats(
        self,
        endpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取端点统计"""
        if endpoint:
            times = list(self.request_times.get(endpoint, []))
            if not times:
                return {}

            return {
                "endpoint": endpoint,
                "count": len(times),
                "min_ms": min(times),
                "max_ms": max(times),
                "avg_ms": sum(times) / len(times),
                "p95_ms": sorted(times)[int(len(times) * 0.95)] if times else 0
            }

        stats = {}
        for ep, times in self.request_times.items():
            if times:
                times_list = list(times)
                stats[ep] = {
                    "endpoint": ep,
                    "count": len(times_list),
                    "min_ms": min(times_list),
                    "max_ms": max(times_list),
                    "avg_ms": sum(times_list) / len(times_list),
                    "p95_ms": sorted(times_list)[int(len(times_list) * 0.95)]
                }

        return stats


# 内置健康检查函数
def check_database_health() -> HealthCheckResult:
    """数据库健康检查（示例）"""
    # 这里可以添加实际的数据库连接检查
    return HealthCheckResult(
        name="database",
        status=HealthStatus.HEALTHY,
        message="数据库连接正常",
        timestamp=datetime.now(),
        duration_ms=5.0
    )


async def check_qbittorrent_connection() -> HealthCheckResult:
    """qBittorrent连接健康检查"""
    try:
        from .qbittorrent_client import QBittorrentClient
        from .config import ConfigManager

        config_manager = ConfigManager()
        config = await config_manager.load_config()

        async with QBittorrentClient(config['qbittorrent']) as client:
            version = await client.get_version()

        return HealthCheckResult(
            name="qbittorrent",
            status=HealthStatus.HEALTHY,
            message=f"qBittorrent连接正常 (版本: {version})",
            timestamp=datetime.now(),
            duration_ms=100.0,
            critical=True
        )
    except Exception as e:
        return HealthCheckResult(
            name="qbittorrent",
            status=HealthStatus.CRITICAL,
            message=f"qBittorrent连接失败: {str(e)}",
            timestamp=datetime.now(),
            duration_ms=0,
            critical=True
        )


async def check_memory_health() -> HealthCheckResult:
    """内存健康检查"""
    try:
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            return HealthCheckResult(
                name="memory",
                status=HealthStatus.CRITICAL,
                message=f"内存使用率过高: {memory.percent:.1f}%",
                timestamp=datetime.now(),
                duration_ms=10.0,
                critical=True
            )
        elif memory.percent > 80:
            return HealthCheckResult(
                name="memory",
                status=HealthStatus.WARNING,
                message=f"内存使用率较高: {memory.percent:.1f}%",
                timestamp=datetime.now(),
                duration_ms=10.0
            )
        else:
            return HealthCheckResult(
                name="memory",
                status=HealthStatus.HEALTHY,
                message=f"内存使用率正常: {memory.percent:.1f}%",
                timestamp=datetime.now(),
                duration_ms=10.0
            )
    except Exception as e:
        return HealthCheckResult(
            name="memory",
            status=HealthStatus.UNKNOWN,
            message=f"无法检查内存状态: {str(e)}",
            timestamp=datetime.now(),
            duration_ms=0
        )


async def check_disk_health() -> HealthCheckResult:
    """磁盘健康检查"""
    try:
        disk = psutil.disk_usage('/')
        usage_percent = (disk.used / disk.total) * 100

        if usage_percent > 95:
            return HealthCheckResult(
                name="disk",
                status=HealthStatus.CRITICAL,
                message=f"磁盘空间严重不足: {usage_percent:.1f}%",
                timestamp=datetime.now(),
                duration_ms=10.0,
                critical=True
            )
        elif usage_percent > 85:
            return HealthCheckResult(
                name="disk",
                status=HealthStatus.WARNING,
                message=f"磁盘空间不足: {usage_percent:.1f}%",
                timestamp=datetime.now(),
                duration_ms=10.0
            )
        else:
            return HealthCheckResult(
                name="disk",
                status=HealthStatus.HEALTHY,
                message=f"磁盘空间充足: {usage_percent:.1f}%",
                timestamp=datetime.now(),
                duration_ms=10.0
            )
    except Exception as e:
        return HealthCheckResult(
            name="disk",
            status=HealthStatus.UNKNOWN,
            message=f"无法检查磁盘状态: {str(e)}",
            timestamp=datetime.now(),
            duration_ms=0
        )


# 全局监控实例
_global_metrics_collector: Optional[MetricsCollector] = None
_global_health_checker: Optional[HealthChecker] = None
_global_system_monitor: Optional[SystemMonitor] = None
_global_alert_manager: Optional[AlertManager] = None
_global_performance_monitor: Optional[PerformanceMonitor] = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器"""
    global _global_metrics_collector
    if _global_metrics_collector is None:
        _global_metrics_collector = MetricsCollector()
    return _global_metrics_collector


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器"""
    global _global_health_checker
    if _global_health_checker is None:
        _global_health_checker = HealthChecker()
    return _global_health_checker


async def initialize_monitoring() -> None:
    """初始化监控系统"""
    global _global_system_monitor, _global_alert_manager, _global_performance_monitor

    # 获取或创建全局实例
    metrics_collector = get_metrics_collector()
    health_checker = get_health_checker()

    # 注册健康检查
    health_checker.register_check("memory", check_memory_health, critical=True)
    health_checker.register_check("disk", check_disk_health, critical=True)
    health_checker.register_check("database", check_database_health)
    health_checker.register_check("qbittorrent", check_qbittorrent_connection, critical=True)

    # 创建并启动系统监控
    _global_system_monitor = SystemMonitor(check_interval=10.0)
    await _global_system_monitor.start(metrics_collector)

    # 创建警报管理器
    _global_alert_manager = AlertManager()

    # 创建性能监控器
    _global_performance_monitor = PerformanceMonitor(metrics_collector)

    logger.info("监控系统初始化完成")


async def shutdown_monitoring() -> None:
    """关闭监控系统"""
    global _global_system_monitor

    if _global_system_monitor:
        await _global_system_monitor.stop()

    logger.info("监控系统已关闭")


async def get_monitoring_report() -> Dict[str, Any]:
    """获取监控报告"""
    metrics_collector = get_metrics_collector()
    health_checker = get_health_checker()
    alert_manager = _global_alert_manager
    performance_monitor = _global_performance_monitor

    # 获取各组件报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "health": await health_checker.get_overall_status().to_dict() if hasattr(health_checker.get_overall_status(), 'to_dict') else health_checker.get_overall_status().value,
        "metrics": metrics_collector.get_stats(),
        "health_checks": health_checker.get_report(),
        "performance": await performance_monitor.get_endpoint_stats() if performance_monitor else {}
    }

    # 添加系统信息
    try:
        report["system"] = {
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": psutil.virtual_memory().total / 1024 / 1024 / 1024,
            "platform": psutil.MACOS if hasattr(psutil, 'MACOS') else "unknown"
        }
    except Exception as e:
        report["system_error"] = str(e)

    # 添加最近警报
    if alert_manager:
        report["recent_alerts"] = await alert_manager.get_recent_alerts(limit=10)

    return report
