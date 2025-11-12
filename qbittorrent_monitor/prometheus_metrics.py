"""
Prometheus监控指标导出模块
提供标准的Prometheus格式指标导出
"""

import time
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict, deque
import re

logger = logging.getLogger(__name__)


@dataclass
class MetricFamily:
    """指标族"""
    name: str
    help_text: str
    type: str  # "counter", "gauge", "histogram", "summary"
    samples: Dict[str, float] = field(default_factory=dict)
    labels: List[str] = field(default_factory=list)


@dataclass
class MetricSample:
    """指标样本"""
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: Optional[float] = None


class PrometheusMetrics:
    """Prometheus指标收集器"""

    def __init__(self, prefix: str = "qbittorrent_monitor"):
        self.prefix = prefix
        self.metrics: Dict[str, MetricFamily] = {}
        self.collectors: List[Callable] = []
        self._lock = asyncio.Lock()

        # 预定义核心指标
        self._init_core_metrics()

        logger.info(f"Prometheus指标收集器初始化完成，前缀: {prefix}")

    def _init_core_metrics(self):
        """初始化核心指标"""
        # 业务指标
        self.register_counter(
            "clipboard_changes_total",
            "剪贴板变化总次数",
            ["source", "result"]
        )

        self.register_counter(
            "magnet_links_detected_total",
            "检测到的磁力链接总数",
            ["protocol"]
        )

        self.register_counter(
            "torrents_added_total",
            "添加到qBittorrent的种子总数",
            ["category", "status"]
        )

        self.register_counter(
            "ai_classifications_total",
            "AI分类总次数",
            ["provider", "model", "category"]
        )

        self.register_counter(
            "classification_errors_total",
            "AI分类错误总次数",
            ["provider", "error_type"]
        )

        # 性能指标
        self.register_gauge(
            "monitoring_interval_seconds",
            "监控间隔时间(秒)"
        )

        self.register_histogram(
            "processing_duration_seconds",
            "处理持续时间(秒)",
            [0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0],
            ["operation"]
        )

        self.register_gauge(
            "cache_size",
            "缓存大小",
            ["cache_type"]
        )

        self.register_gauge(
            "cache_hit_ratio",
            "缓存命中率",
            ["cache_type"]
        )

        # 系统指标
        self.register_gauge(
            "memory_usage_bytes",
            "内存使用量(字节)",
            ["type"]
        )

        self.register_gauge(
            "cpu_usage_percent",
            "CPU使用率(百分比)"
        )

        self.register_gauge(
            "active_connections",
            "活跃连接数",
            ["type"]
        )

        self.register_gauge(
            "uptime_seconds",
            "运行时间(秒)"
        )

        # 错误指标
        self.register_counter(
            "errors_total",
            "错误总次数",
            ["component", "error_type"]
        )

        self.register_counter(
            "retries_total",
            "重试总次数",
            ["component", "reason"]
        )

    def register_counter(self, name: str, help_text: str, labels: List[str] = None) -> str:
        """注册计数器指标"""
        full_name = f"{self.prefix}_{name}"
        self.metrics[full_name] = MetricFamily(
            name=full_name,
            help_text=help_text,
            type="counter",
            labels=labels or []
        )
        logger.debug(f"注册计数器指标: {full_name}")
        return full_name

    def register_gauge(self, name: str, help_text: str, labels: List[str] = None) -> str:
        """注册仪表盘指标"""
        full_name = f"{self.prefix}_{name}"
        self.metrics[full_name] = MetricFamily(
            name=full_name,
            help_text=help_text,
            type="gauge",
            labels=labels or []
        )
        logger.debug(f"注册仪表盘指标: {full_name}")
        return full_name

    def register_histogram(self, name: str, help_text: str, buckets: List[float], labels: List[str] = None) -> str:
        """注册直方图指标"""
        full_name = f"{self.prefix}_{name}"
        self.metrics[full_name] = MetricFamily(
            name=full_name,
            help_text=help_text,
            type="histogram",
            labels=labels or []
        )
        # 存储桶信息存储在labels中
        self.metrics[full_name].labels = (labels or []) + ["le"]
        logger.debug(f"注册直方图指标: {full_name}")
        return full_name

    def register_summary(self, name: str, help_text: str, labels: List[str] = None) -> str:
        """注册摘要指标"""
        full_name = f"{self.prefix}_{name}"
        self.metrics[full_name] = MetricFamily(
            name=full_name,
            help_text=help_text,
            type="summary",
            labels=labels or []
        )
        logger.debug(f"注册摘要指标: {full_name}")
        return full_name

    async def increment_counter(self, name: str, value: float = 1, labels: Dict[str, str] = None):
        """递增计数器"""
        full_name = name if name.startswith(self.prefix) else f"{self.prefix}_{name}"

        async with self._lock:
            if full_name not in self.metrics:
                logger.warning(f"指标未注册: {full_name}")
                return

            metric = self.metrics[full_name]
            if metric.type != "counter":
                logger.warning(f"指标类型不匹配: {full_name} 期望 counter，实际 {metric.type}")
                return

            label_key = self._make_label_key(labels or {})
            metric.samples[label_key] = metric.samples.get(label_key, 0) + value

    async def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        """设置仪表盘值"""
        full_name = name if name.startswith(self.prefix) else f"{self.prefix}_{name}"

        async with self._lock:
            if full_name not in self.metrics:
                logger.warning(f"指标未注册: {full_name}")
                return

            metric = self.metrics[full_name]
            if metric.type != "gauge":
                logger.warning(f"指标类型不匹配: {full_name} 期望 gauge，实际 {metric.type}")
                return

            label_key = self._make_label_key(labels or {})
            metric.samples[label_key] = value

    async def observe_histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        """观察直方图值"""
        full_name = name if name.startswith(self.prefix) else f"{self.prefix}_{name}"

        async with self._lock:
            if full_name not in self.metrics:
                logger.warning(f"指标未注册: {full_name}")
                return

            metric = self.metrics[full_name]
            if metric.type != "histogram":
                logger.warning(f"指标类型不匹配: {full_name} 期望 histogram，实际 {metric.type}")
                return

            # 获取桶边界（从指标注释或默认值）
            buckets = self._get_histogram_buckets(full_name)

            label_dict = labels or {}
            for bucket in buckets:
                bucket_labels = label_dict.copy()
                bucket_labels["le"] = str(bucket)
                bucket_key = self._make_label_key(bucket_labels)

                if value <= bucket:
                    metric.samples[bucket_key] = metric.samples.get(bucket_key, 0) + 1

            # +Inf桶
            inf_labels = label_dict.copy()
            inf_labels["le"] = "+Inf"
            inf_key = self._make_label_key(inf_labels)
            metric.samples[inf_key] = metric.samples.get(inf_key, 0) + 1

            # 总数和总和
            count_labels = label_dict.copy()
            count_key = self._make_label_key({**count_labels, "_suffix": "_count"})
            sum_key = self._make_label_key({**count_labels, "_suffix": "_sum"})

            metric.samples[count_key] = metric.samples.get(count_key, 0) + 1
            metric.samples[sum_key] = metric.samples.get(sum_key, 0) + value

    def _get_histogram_buckets(self, full_name: str) -> List[float]:
        """获取直方图桶边界"""
        # 这里简化处理，实际应该从注册时保存的桶信息获取
        default_buckets = [0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0]
        return default_buckets

    def _make_label_key(self, labels: Dict[str, str]) -> str:
        """创建标签键"""
        if not labels:
            return ""

        # 过滤掉特殊标签
        filtered_labels = {k: v for k, v in labels.items() if not k.startswith("_")}

        if not filtered_labels:
            return ""

        # 按标签名排序确保一致性
        sorted_labels = sorted(filtered_labels.items())
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted_labels)
        return f"{{{label_str}}}"

    def register_collector(self, collector: Callable[[], List[MetricSample]]):
        """注册自定义收集器"""
        self.collectors.append(collector)
        logger.debug(f"注册自定义收集器: {collector.__name__}")

    async def collect(self) -> str:
        """收集所有指标并返回Prometheus格式"""
        await self._lock.acquire()
        try:
            # 运行自定义收集器
            for collector in self.collectors:
                try:
                    samples = await collector() if asyncio.iscoroutinefunction(collector) else collector()
                    for sample in samples:
                        await self._add_sample(sample)
                except Exception as e:
                    logger.error(f"收集器执行失败 {collector.__name__}: {e}")

            # 生成Prometheus格式输出
            output = []

            for metric in self.metrics.values():
                if metric.samples:
                    # 添加指标元数据
                    output.append(f"# HELP {metric.name} {metric.help_text}")
                    output.append(f"# TYPE {metric.name} {metric.type}")

                    # 添加样本数据
                    for label_key, value in metric.samples.items():
                        if "_suffix" in label_key:
                            continue  # 跳过特殊标记

                        sample_name = metric.name

                        # 处理直方图的特殊后缀
                        if "_count" in label_key:
                            sample_name += "_count"
                            label_key = label_key.replace("_count", "").replace("{}", "")
                        elif "_sum" in label_key:
                            sample_name += "_sum"
                            label_key = label_key.replace("_sum", "").replace("{}", "")

                        if label_key:
                            output.append(f"{sample_name}{label_key} {value}")
                        else:
                            output.append(f"{sample_name} {value}")

            return "\n".join(output)

        finally:
            await self._lock.release()

    async def _add_sample(self, sample: MetricSample):
        """添加指标样本"""
        full_name = sample.name if sample.name.startswith(self.prefix) else f"{self.prefix}_{sample.name}"

        if full_name not in self.metrics:
            # 自动注册指标
            self.register_gauge(full_name, "自动注册的指标")

        metric = self.metrics[full_name]
        label_key = self._make_label_key(sample.labels)
        metric.samples[label_key] = sample.value


class MetricsCollectors:
    """指标收集器集合"""

    @staticmethod
    def system_metrics_collector() -> Callable[[], List[MetricSample]]:
        """系统指标收集器"""
        def collect_system_metrics() -> List[MetricSample]:
            samples = []

            try:
                import psutil

                # CPU使用率
                cpu_percent = psutil.cpu_percent(interval=1)
                samples.append(MetricSample(
                    name="cpu_usage_percent",
                    value=cpu_percent
                ))

                # 内存使用
                memory = psutil.virtual_memory()
                samples.append(MetricSample(
                    name="memory_usage_bytes",
                    value=memory.used,
                    labels={"type": "used"}
                ))
                samples.append(MetricSample(
                    name="memory_usage_bytes",
                    value=memory.available,
                    labels={"type": "available"}
                ))

                # 磁盘使用
                disk = psutil.disk_usage(".")
                samples.append(MetricSample(
                    name="disk_usage_bytes",
                    value=disk.used,
                    labels={"type": "used", "mountpoint": "/"}
                ))
                samples.append(MetricSample(
                    name="disk_usage_bytes",
                    value=disk.free,
                    labels={"type": "free", "mountpoint": "/"}
                ))

                # 网络IO
                net_io = psutil.net_io_counters()
                samples.append(MetricSample(
                    name="network_io_bytes_total",
                    value=net_io.bytes_sent,
                    labels={"direction": "sent"}
                ))
                samples.append(MetricSample(
                    name="network_io_bytes_total",
                    value=net_io.bytes_recv,
                    labels={"direction": "received"}
                ))

            except ImportError:
                logger.warning("psutil未安装，无法收集系统指标")
            except Exception as e:
                logger.error(f"收集系统指标失败: {e}")

            return samples

        return collect_system_metrics

    @staticmethod
    def qbt_metrics_collector(qbt_client) -> Callable[[], List[MetricSample]]:
        """qBittorrent指标收集器"""
        def collect_qbt_metrics() -> List[MetricSample]:
            samples = []

            if not qbt_client:
                return samples

            try:
                # 获取种子统计
                # 这里需要根据实际的qBittorrent客户端API实现
                # 示例代码，需要适配实际的API

                samples.append(MetricSample(
                    name="qbt_torrents_total",
                    value=0,  # 实际应该从API获取
                    labels={"status": "all"}
                ))

            except Exception as e:
                logger.error(f"收集qBittorrent指标失败: {e}")

            return samples

        return collect_qbt_metrics


class PrometheusServer:
    """Prometheus指标HTTP服务器"""

    def __init__(self, metrics: PrometheusMetrics, host: str = "0.0.0.0", port: int = 8091):
        self.metrics = metrics
        self.host = host
        self.port = port
        self.runner = None

    async def start(self):
        """启动Prometheus指标服务"""
        from aiohttp import web
        import aiohttp_cors

        app = web.Application()

        # 配置CORS
        cors = aiohttp_cors.setup(app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })

        # 注册指标端点
        app.router.add_get("/metrics", self.metrics_handler)

        # 添加CORS
        for route in list(app.router.routes()):
            cors.add(route)

        # 启动服务器
        self.runner = web.AppRunner(app)
        await self.runner.setup()

        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()

        logger.info(f"Prometheus指标服务已启动: http://{self.host}:{port}/metrics")

    async def stop(self):
        """停止Prometheus指标服务"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Prometheus指标服务已停止")

    async def metrics_handler(self, request):
        """指标HTTP处理器"""
        try:
            metrics_output = await self.metrics.collect()
            return web.Response(
                text=metrics_output,
                content_type="text/plain; version=0.0.4; charset=utf-8"
            )
        except Exception as e:
            logger.error(f"生成指标输出失败: {e}")
            return web.Response(
                text=f"# Error generating metrics: {str(e)}",
                content_type="text/plain",
                status=500
            )