#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能监控模块

提供系统性能监控、指标收集和性能分析功能：
- 实时性能指标收集
- 内存使用监控
- CPU使用率监控
- 网络IO监控
- 磁盘IO监控
- 自定义指标收集
- 性能报告生成
- 异常检测和告警
"""

import asyncio
import logging
import psutil
import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path


@dataclass
class PerformanceMetric:
    """性能指标数据类"""
    name: str
    value: Union[int, float]
    timestamp: datetime
    unit: str = ""
    category: str = "general"
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'name': self.name,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'unit': self.unit,
            'category': self.category,
            'tags': self.tags
        }


@dataclass
class SystemStats:
    """系统统计信息"""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used: int = 0
    memory_available: int = 0
    disk_usage_percent: float = 0.0
    disk_read_bytes: int = 0
    disk_write_bytes: int = 0
    network_sent_bytes: int = 0
    network_recv_bytes: int = 0
    process_count: int = 0
    thread_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'memory_used': self.memory_used,
            'memory_available': self.memory_available,
            'disk_usage_percent': self.disk_usage_percent,
            'disk_read_bytes': self.disk_read_bytes,
            'disk_write_bytes': self.disk_write_bytes,
            'network_sent_bytes': self.network_sent_bytes,
            'network_recv_bytes': self.network_recv_bytes,
            'process_count': self.process_count,
            'thread_count': self.thread_count,
            'timestamp': self.timestamp.isoformat()
        }


class PerformanceCollector:
    """性能数据收集器"""
    
    def __init__(self, collection_interval: float = 1.0):
        self.collection_interval = collection_interval
        self.logger = logging.getLogger('PerformanceCollector')
        
        # 数据存储
        self.metrics: deque = deque(maxlen=10000)  # 最多保存10000个指标
        self.system_stats: deque = deque(maxlen=1000)  # 最多保存1000个系统统计
        
        # 收集状态
        self._collecting = False
        self._collection_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
        # 自定义指标收集器
        self._custom_collectors: Dict[str, Callable[[], Dict[str, Any]]] = {}
        
        # 线程池用于同步操作
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="perf_collector")
        
        # 清理状态
        self._is_cleaned_up = False
    
    def add_custom_collector(self, name: str, collector_func: Callable[[], Dict[str, Any]]):
        """添加自定义指标收集器"""
        self._custom_collectors[name] = collector_func
        self.logger.info(f"添加自定义收集器: {name}")
    
    def remove_custom_collector(self, name: str):
        """移除自定义指标收集器"""
        if name in self._custom_collectors:
            del self._custom_collectors[name]
            self.logger.info(f"移除自定义收集器: {name}")
    
    async def start_collection(self):
        """开始性能数据收集"""
        if self._collecting:
            return
        
        async with self._lock:
            if self._collecting:
                return
            
            self._collecting = True
            self._collection_task = asyncio.create_task(self._collection_loop())
            self.logger.info("性能数据收集已启动")
    
    async def stop_collection(self):
        """停止性能数据收集"""
        if not self._collecting:
            return
        
        async with self._lock:
            if not self._collecting:
                return
            
            self._collecting = False
            if self._collection_task:
                self._collection_task.cancel()
                try:
                    await self._collection_task
                except asyncio.CancelledError:
                    pass
                self._collection_task = None
            
            self.logger.info("性能数据收集已停止")
    
    async def _collection_loop(self):
        """数据收集循环"""
        try:
            while self._collecting:
                try:
                    # 收集系统统计
                    stats = await self._collect_system_stats()
                    if stats:
                        self.system_stats.append(stats)
                    
                    # 收集自定义指标
                    await self._collect_custom_metrics()
                    
                    # 等待下次收集
                    await asyncio.sleep(self.collection_interval)
                    
                except Exception as e:
                    self.logger.error(f"收集性能数据时出错: {str(e)}")
                    await asyncio.sleep(self.collection_interval)
        
        except asyncio.CancelledError:
            self.logger.debug("性能数据收集循环被取消")
        except Exception as e:
            self.logger.error(f"性能数据收集循环异常: {str(e)}")
    
    async def _collect_system_stats(self) -> Optional[SystemStats]:
        """收集系统统计信息"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(self._executor, self._get_system_stats)
        except Exception as e:
            self.logger.error(f"收集系统统计时出错: {str(e)}")
            return None
    
    def _get_system_stats(self) -> SystemStats:
        """获取系统统计信息（同步方法）"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # 内存信息
            memory = psutil.virtual_memory()
            
            # 磁盘信息
            disk = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # 网络信息
            network_io = psutil.net_io_counters()
            
            # 进程信息
            process_count = len(psutil.pids())
            
            # 当前进程的线程数
            current_process = psutil.Process()
            thread_count = current_process.num_threads()
            
            return SystemStats(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used=memory.used,
                memory_available=memory.available,
                disk_usage_percent=disk.percent,
                disk_read_bytes=disk_io.read_bytes if disk_io else 0,
                disk_write_bytes=disk_io.write_bytes if disk_io else 0,
                network_sent_bytes=network_io.bytes_sent if network_io else 0,
                network_recv_bytes=network_io.bytes_recv if network_io else 0,
                process_count=process_count,
                thread_count=thread_count
            )
        
        except Exception as e:
            self.logger.error(f"获取系统统计时出错: {str(e)}")
            return SystemStats()
    
    async def _collect_custom_metrics(self):
        """收集自定义指标"""
        for name, collector_func in self._custom_collectors.items():
            try:
                loop = asyncio.get_event_loop()
                metrics_data = await loop.run_in_executor(self._executor, collector_func)
                
                if isinstance(metrics_data, dict):
                    for metric_name, value in metrics_data.items():
                        metric = PerformanceMetric(
                            name=metric_name,
                            value=value,
                            timestamp=datetime.now(),
                            category=name,
                            tags={'collector': name}
                        )
                        self.metrics.append(metric)
            
            except Exception as e:
                self.logger.error(f"收集自定义指标 {name} 时出错: {str(e)}")
    
    def add_metric(self, name: str, value: Union[int, float], 
                   unit: str = "", category: str = "custom", 
                   tags: Optional[Dict[str, str]] = None):
        """手动添加指标"""
        metric = PerformanceMetric(
            name=name,
            value=value,
            timestamp=datetime.now(),
            unit=unit,
            category=category,
            tags=tags or {}
        )
        self.metrics.append(metric)
    
    def get_recent_metrics(self, count: int = 100) -> List[PerformanceMetric]:
        """获取最近的指标"""
        return list(self.metrics)[-count:]
    
    def get_recent_system_stats(self, count: int = 100) -> List[SystemStats]:
        """获取最近的系统统计"""
        return list(self.system_stats)[-count:]
    
    def get_metrics_by_category(self, category: str, 
                               since: Optional[datetime] = None) -> List[PerformanceMetric]:
        """按类别获取指标"""
        result = []
        for metric in self.metrics:
            if metric.category == category:
                if since is None or metric.timestamp >= since:
                    result.append(metric)
        return result
    
    def clear_old_data(self, older_than: timedelta = timedelta(hours=24)):
        """清理旧数据"""
        cutoff_time = datetime.now() - older_than
        
        # 清理旧指标
        while self.metrics and self.metrics[0].timestamp < cutoff_time:
            self.metrics.popleft()
        
        # 清理旧系统统计
        while self.system_stats and self.system_stats[0].timestamp < cutoff_time:
            self.system_stats.popleft()
        
        self.logger.info(f"清理了 {cutoff_time} 之前的旧数据")
    
    async def cleanup(self):
        """清理资源"""
        if self._is_cleaned_up:
            return
        
        self.logger.info("开始清理PerformanceCollector资源...")
        
        try:
            # 停止数据收集
            await self.stop_collection()
            
            # 关闭线程池
            if self._executor:
                self._executor.shutdown(wait=True)
            
            # 清理数据
            self.metrics.clear()
            self.system_stats.clear()
            self._custom_collectors.clear()
            
            self._is_cleaned_up = True
            self.logger.info("PerformanceCollector资源清理完成")
        
        except Exception as e:
            self.logger.error(f"清理PerformanceCollector资源时出错: {str(e)}")


class PerformanceAnalyzer:
    """性能分析器"""
    
    def __init__(self, collector: PerformanceCollector):
        self.collector = collector
        self.logger = logging.getLogger('PerformanceAnalyzer')
    
    def analyze_cpu_usage(self, duration_minutes: int = 10) -> Dict[str, Any]:
        """分析CPU使用情况"""
        since = datetime.now() - timedelta(minutes=duration_minutes)
        stats = [s for s in self.collector.system_stats if s.timestamp >= since]
        
        if not stats:
            return {'error': '没有足够的数据进行分析'}
        
        cpu_values = [s.cpu_percent for s in stats]
        
        return {
            'average': sum(cpu_values) / len(cpu_values),
            'max': max(cpu_values),
            'min': min(cpu_values),
            'samples': len(cpu_values),
            'duration_minutes': duration_minutes,
            'high_usage_periods': len([v for v in cpu_values if v > 80])
        }
    
    def analyze_memory_usage(self, duration_minutes: int = 10) -> Dict[str, Any]:
        """分析内存使用情况"""
        since = datetime.now() - timedelta(minutes=duration_minutes)
        stats = [s for s in self.collector.system_stats if s.timestamp >= since]
        
        if not stats:
            return {'error': '没有足够的数据进行分析'}
        
        memory_values = [s.memory_percent for s in stats]
        memory_used_values = [s.memory_used for s in stats]
        
        return {
            'average_percent': sum(memory_values) / len(memory_values),
            'max_percent': max(memory_values),
            'min_percent': min(memory_values),
            'average_used_mb': sum(memory_used_values) / len(memory_used_values) / 1024 / 1024,
            'max_used_mb': max(memory_used_values) / 1024 / 1024,
            'samples': len(memory_values),
            'duration_minutes': duration_minutes,
            'high_usage_periods': len([v for v in memory_values if v > 80])
        }
    
    def detect_performance_issues(self) -> List[Dict[str, Any]]:
        """检测性能问题"""
        issues = []
        
        # 检查最近5分钟的数据
        recent_stats = self.collector.get_recent_system_stats(300)  # 5分钟的数据
        
        if not recent_stats:
            return issues
        
        # CPU使用率过高
        high_cpu_count = sum(1 for s in recent_stats if s.cpu_percent > 90)
        if high_cpu_count > len(recent_stats) * 0.3:  # 超过30%的时间CPU使用率过高
            issues.append({
                'type': 'high_cpu_usage',
                'severity': 'warning',
                'message': f'CPU使用率过高，{high_cpu_count}/{len(recent_stats)} 个采样点超过90%',
                'suggestion': '检查是否有CPU密集型任务运行'
            })
        
        # 内存使用率过高
        high_memory_count = sum(1 for s in recent_stats if s.memory_percent > 85)
        if high_memory_count > len(recent_stats) * 0.3:
            issues.append({
                'type': 'high_memory_usage',
                'severity': 'warning',
                'message': f'内存使用率过高，{high_memory_count}/{len(recent_stats)} 个采样点超过85%',
                'suggestion': '检查内存泄漏或考虑增加内存'
            })
        
        # 磁盘使用率过高
        high_disk_count = sum(1 for s in recent_stats if s.disk_usage_percent > 90)
        if high_disk_count > 0:
            issues.append({
                'type': 'high_disk_usage',
                'severity': 'critical',
                'message': f'磁盘使用率过高，超过90%',
                'suggestion': '清理磁盘空间或扩展存储'
            })
        
        return issues
    
    def generate_performance_report(self, duration_hours: int = 1) -> Dict[str, Any]:
        """生成性能报告"""
        since = datetime.now() - timedelta(hours=duration_hours)
        stats = [s for s in self.collector.system_stats if s.timestamp >= since]
        
        if not stats:
            return {'error': '没有足够的数据生成报告'}
        
        # CPU分析
        cpu_analysis = self.analyze_cpu_usage(duration_hours * 60)
        
        # 内存分析
        memory_analysis = self.analyze_memory_usage(duration_hours * 60)
        
        # 性能问题检测
        issues = self.detect_performance_issues()
        
        # 自定义指标统计
        custom_metrics = {}
        for metric in self.collector.metrics:
            if metric.timestamp >= since and metric.category != 'system':
                category = metric.category
                if category not in custom_metrics:
                    custom_metrics[category] = []
                custom_metrics[category].append(metric.value)
        
        # 计算自定义指标的统计信息
        custom_stats = {}
        for category, values in custom_metrics.items():
            if values:
                custom_stats[category] = {
                    'count': len(values),
                    'average': sum(values) / len(values),
                    'max': max(values),
                    'min': min(values)
                }
        
        return {
            'report_period': {
                'duration_hours': duration_hours,
                'start_time': since.isoformat(),
                'end_time': datetime.now().isoformat(),
                'samples_count': len(stats)
            },
            'cpu_analysis': cpu_analysis,
            'memory_analysis': memory_analysis,
            'custom_metrics': custom_stats,
            'performance_issues': issues,
            'summary': {
                'total_issues': len(issues),
                'critical_issues': len([i for i in issues if i['severity'] == 'critical']),
                'warning_issues': len([i for i in issues if i['severity'] == 'warning'])
            }
        }


class PerformanceMonitor:
    """性能监控主类"""
    
    def __init__(self, collection_interval: float = 1.0, 
                 auto_cleanup_hours: int = 24,
                 report_file: Optional[str] = None):
        self.logger = logging.getLogger('PerformanceMonitor')
        
        # 初始化组件
        self.collector = PerformanceCollector(collection_interval)
        self.analyzer = PerformanceAnalyzer(self.collector)
        
        # 配置
        self.auto_cleanup_hours = auto_cleanup_hours
        self.report_file = Path(report_file) if report_file else None
        
        # 自动清理任务
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 3600  # 1小时清理一次
        
        # 清理状态
        self._is_cleaned_up = False
    
    async def start(self):
        """启动性能监控"""
        self.logger.info("启动性能监控...")
        
        # 启动数据收集
        await self.collector.start_collection()
        
        # 启动自动清理任务
        self._cleanup_task = asyncio.create_task(self._auto_cleanup_loop())
        
        # 添加默认的自定义收集器
        self._setup_default_collectors()
        
        self.logger.info("性能监控已启动")
    
    async def stop(self):
        """停止性能监控"""
        self.logger.info("停止性能监控...")
        
        # 停止数据收集
        await self.collector.stop_collection()
        
        # 停止自动清理任务
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        self.logger.info("性能监控已停止")
    
    def _setup_default_collectors(self):
        """设置默认的自定义收集器"""
        # 添加应用程序特定的指标收集器
        def collect_app_metrics():
            """收集应用程序指标"""
            try:
                import gc
                return {
                    'gc_objects': len(gc.get_objects()),
                    'gc_collections_gen0': gc.get_count()[0],
                    'gc_collections_gen1': gc.get_count()[1],
                    'gc_collections_gen2': gc.get_count()[2]
                }
            except Exception:
                return {}
        
        self.collector.add_custom_collector('app_metrics', collect_app_metrics)
    
    async def _auto_cleanup_loop(self):
        """自动清理循环"""
        try:
            while True:
                await asyncio.sleep(self._cleanup_interval)
                
                try:
                    # 清理旧数据
                    self.collector.clear_old_data(timedelta(hours=self.auto_cleanup_hours))
                    
                    # 生成并保存报告（如果配置了报告文件）
                    if self.report_file:
                        await self._save_performance_report()
                
                except Exception as e:
                    self.logger.error(f"自动清理时出错: {str(e)}")
        
        except asyncio.CancelledError:
            self.logger.debug("自动清理循环被取消")
        except Exception as e:
            self.logger.error(f"自动清理循环异常: {str(e)}")
    
    async def _save_performance_report(self):
        """保存性能报告"""
        try:
            report = self.analyzer.generate_performance_report(1)  # 1小时报告
            
            # 确保目录存在
            self.report_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存报告
            with open(self.report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"性能报告已保存到: {self.report_file}")
        
        except Exception as e:
            self.logger.error(f"保存性能报告时出错: {str(e)}")
    
    def add_custom_collector(self, name: str, collector_func: Callable[[], Dict[str, Any]]):
        """添加自定义指标收集器"""
        self.collector.add_custom_collector(name, collector_func)
    
    def add_metric(self, name: str, value: Union[int, float], 
                   unit: str = "", category: str = "custom", 
                   tags: Optional[Dict[str, str]] = None):
        """添加自定义指标"""
        self.collector.add_metric(name, value, unit, category, tags)
    
    def get_current_stats(self) -> Optional[SystemStats]:
        """获取当前系统统计"""
        recent_stats = self.collector.get_recent_system_stats(1)
        return recent_stats[0] if recent_stats else None
    
    def get_performance_report(self, duration_hours: int = 1) -> Dict[str, Any]:
        """获取性能报告"""
        return self.analyzer.generate_performance_report(duration_hours)
    
    def detect_issues(self) -> List[Dict[str, Any]]:
        """检测性能问题"""
        return self.analyzer.detect_performance_issues()
    
    async def cleanup(self):
        """清理资源"""
        if self._is_cleaned_up:
            return
        
        self.logger.info("开始清理PerformanceMonitor资源...")
        
        try:
            # 停止监控
            await self.stop()
            
            # 清理收集器
            await self.collector.cleanup()
            
            self._is_cleaned_up = True
            self.logger.info("PerformanceMonitor资源清理完成")
        
        except Exception as e:
            self.logger.error(f"清理PerformanceMonitor资源时出错: {str(e)}")


# 全局性能监控实例
_global_monitor: Optional[PerformanceMonitor] = None


def get_global_monitor() -> Optional[PerformanceMonitor]:
    """获取全局性能监控实例"""
    return _global_monitor


async def setup_global_monitor(collection_interval: float = 1.0,
                              auto_cleanup_hours: int = 24,
                              report_file: Optional[str] = None) -> PerformanceMonitor:
    """设置全局性能监控实例"""
    global _global_monitor
    
    if _global_monitor:
        await _global_monitor.cleanup()
    
    _global_monitor = PerformanceMonitor(
        collection_interval=collection_interval,
        auto_cleanup_hours=auto_cleanup_hours,
        report_file=report_file
    )
    
    await _global_monitor.start()
    return _global_monitor


async def cleanup_global_monitor():
    """清理全局性能监控实例"""
    global _global_monitor
    
    if _global_monitor:
        await _global_monitor.cleanup()
        _global_monitor = None