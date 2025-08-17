#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志优化模块

提供高级日志功能和性能优化：
- 智能日志级别调整
- 日志性能优化
- 结构化日志记录
- 日志聚合和分析
- 异步日志处理
- 日志轮转和清理
- 敏感信息过滤
- 日志监控和告警
"""

import asyncio
import logging
import logging.handlers
import json
import re
import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable, Set
from concurrent.futures import ThreadPoolExecutor
import queue
import sys
import traceback
from enum import Enum


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


@dataclass
class LogEntry:
    """结构化日志条目"""
    timestamp: datetime
    level: str
    logger_name: str
    message: str
    module: str = ""
    function: str = ""
    line_number: int = 0
    thread_id: int = 0
    process_id: int = 0
    extra_data: Dict[str, Any] = field(default_factory=dict)
    exception_info: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'logger_name': self.logger_name,
            'message': self.message,
            'module': self.module,
            'function': self.function,
            'line_number': self.line_number,
            'thread_id': self.thread_id,
            'process_id': self.process_id,
            'extra_data': self.extra_data,
            'exception_info': self.exception_info
        }
    
    def to_json(self) -> str:
        """转换为JSON格式"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class SensitiveDataFilter:
    """敏感数据过滤器"""
    
    def __init__(self):
        # 敏感信息的正则表达式模式
        self.patterns = {
            'password': re.compile(r'(password|pwd|pass)\s*[:=]\s*["\']?([^\s"\',}]+)', re.IGNORECASE),
            'token': re.compile(r'(token|key|secret)\s*[:=]\s*["\']?([^\s"\',}]+)', re.IGNORECASE),
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'ip_address': re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
            'credit_card': re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
            'phone': re.compile(r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b')
        }
        
        # 替换文本
        self.replacements = {
            'password': '***PASSWORD***',
            'token': '***TOKEN***',
            'email': '***EMAIL***',
            'ip_address': '***IP***',
            'credit_card': '***CARD***',
            'phone': '***PHONE***'
        }
    
    def filter_message(self, message: str) -> str:
        """过滤消息中的敏感信息"""
        filtered_message = message
        
        for pattern_name, pattern in self.patterns.items():
            replacement = self.replacements.get(pattern_name, '***FILTERED***')
            
            if pattern_name in ['password', 'token']:
                # 对于密码和令牌，只替换值部分
                def replace_func(match):
                    return f"{match.group(1)}={replacement}"
                filtered_message = pattern.sub(replace_func, filtered_message)
            else:
                # 对于其他类型，直接替换整个匹配
                filtered_message = pattern.sub(replacement, filtered_message)
        
        return filtered_message
    
    def add_pattern(self, name: str, pattern: str, replacement: str = '***FILTERED***'):
        """添加自定义过滤模式"""
        self.patterns[name] = re.compile(pattern, re.IGNORECASE)
        self.replacements[name] = replacement


class AsyncLogHandler(logging.Handler):
    """异步日志处理器"""
    
    def __init__(self, target_handler: logging.Handler, queue_size: int = 10000):
        super().__init__()
        self.target_handler = target_handler
        self.log_queue = queue.Queue(maxsize=queue_size)
        self.worker_thread = None
        self.shutdown_event = threading.Event()
        self.sensitive_filter = SensitiveDataFilter()
        
        # 启动工作线程
        self._start_worker()
    
    def _start_worker(self):
        """启动工作线程"""
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name="AsyncLogWorker",
            daemon=True
        )
        self.worker_thread.start()
    
    def _worker_loop(self):
        """工作线程循环"""
        while not self.shutdown_event.is_set():
            try:
                # 获取日志记录，超时1秒
                record = self.log_queue.get(timeout=1.0)
                if record is None:  # 停止信号
                    break
                
                # 过滤敏感信息
                if hasattr(record, 'msg') and isinstance(record.msg, str):
                    record.msg = self.sensitive_filter.filter_message(record.msg)
                
                # 处理日志记录
                self.target_handler.emit(record)
                self.log_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                # 避免日志处理错误导致程序崩溃
                print(f"AsyncLogHandler error: {e}", file=sys.stderr)
    
    def emit(self, record):
        """发送日志记录"""
        try:
            # 非阻塞方式放入队列
            self.log_queue.put_nowait(record)
        except queue.Full:
            # 队列满时丢弃最旧的记录
            try:
                self.log_queue.get_nowait()
                self.log_queue.put_nowait(record)
            except queue.Empty:
                pass
    
    def close(self):
        """关闭处理器"""
        # 发送停止信号
        try:
            self.log_queue.put_nowait(None)
        except queue.Full:
            pass
        
        # 设置停止事件
        self.shutdown_event.set()
        
        # 等待工作线程结束
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)
        
        # 关闭目标处理器
        self.target_handler.close()
        
        super().close()


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def __init__(self, include_extra: bool = True, json_format: bool = False):
        super().__init__()
        self.include_extra = include_extra
        self.json_format = json_format
    
    def format(self, record):
        """格式化日志记录"""
        # 创建结构化日志条目
        log_entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created),
            level=record.levelname,
            logger_name=record.name,
            message=record.getMessage(),
            module=record.module if hasattr(record, 'module') else '',
            function=record.funcName if hasattr(record, 'funcName') else '',
            line_number=record.lineno if hasattr(record, 'lineno') else 0,
            thread_id=record.thread if hasattr(record, 'thread') else 0,
            process_id=record.process if hasattr(record, 'process') else 0
        )
        
        # 添加异常信息
        if record.exc_info:
            log_entry.exception_info = self.formatException(record.exc_info)
        
        # 添加额外数据
        if self.include_extra:
            extra_data = {}
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                              'filename', 'module', 'lineno', 'funcName', 'created',
                              'msecs', 'relativeCreated', 'thread', 'threadName',
                              'processName', 'process', 'exc_info', 'exc_text', 'stack_info']:
                    extra_data[key] = value
            log_entry.extra_data = extra_data
        
        # 返回格式化结果
        if self.json_format:
            return log_entry.to_json()
        else:
            return self._format_text(log_entry)
    
    def _format_text(self, log_entry: LogEntry) -> str:
        """格式化为文本格式"""
        parts = [
            log_entry.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            f"[{log_entry.level}]",
            f"{log_entry.logger_name}",
            f"({log_entry.module}:{log_entry.line_number})",
            log_entry.message
        ]
        
        result = " ".join(parts)
        
        # 添加额外数据
        if log_entry.extra_data:
            extra_str = json.dumps(log_entry.extra_data, ensure_ascii=False)
            result += f" | Extra: {extra_str}"
        
        # 添加异常信息
        if log_entry.exception_info:
            result += f"\n{log_entry.exception_info}"
        
        return result


class LogAnalyzer:
    """日志分析器"""
    
    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self.log_entries: deque = deque(maxlen=max_entries)
        self.error_patterns: Dict[str, int] = defaultdict(int)
        self.warning_patterns: Dict[str, int] = defaultdict(int)
        self.performance_metrics: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def add_log_entry(self, record: logging.LogRecord):
        """添加日志条目进行分析"""
        with self._lock:
            # 创建日志条目
            entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created),
                level=record.levelname,
                logger_name=record.name,
                message=record.getMessage(),
                module=getattr(record, 'module', ''),
                function=getattr(record, 'funcName', ''),
                line_number=getattr(record, 'lineno', 0)
            )
            
            self.log_entries.append(entry)
            
            # 分析错误和警告模式
            if record.levelno >= logging.ERROR:
                pattern = self._extract_error_pattern(record.getMessage())
                self.error_patterns[pattern] += 1
            elif record.levelno == logging.WARNING:
                pattern = self._extract_error_pattern(record.getMessage())
                self.warning_patterns[pattern] += 1
            
            # 提取性能指标
            self._extract_performance_metrics(record)
    
    def _extract_error_pattern(self, message: str) -> str:
        """提取错误模式"""
        # 移除具体的数值、路径等变化的部分
        pattern = re.sub(r'\d+', 'N', message)
        pattern = re.sub(r'/[^\s]+', '/PATH', pattern)
        pattern = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'EMAIL', pattern)
        return pattern[:200]  # 限制长度
    
    def _extract_performance_metrics(self, record: logging.LogRecord):
        """提取性能指标"""
        message = record.getMessage()
        
        # 查找时间相关的指标
        time_patterns = [
            (r'took\s+(\d+(?:\.\d+)?)\s*(?:ms|milliseconds?)', 'response_time_ms'),
            (r'duration[:\s]+(\d+(?:\.\d+)?)\s*(?:s|seconds?)', 'duration_seconds'),
            (r'elapsed[:\s]+(\d+(?:\.\d+)?)\s*(?:s|seconds?)', 'elapsed_seconds'),
            (r'processed\s+(\d+)\s+items?', 'items_processed'),
            (r'memory\s+usage[:\s]+(\d+(?:\.\d+)?)\s*(?:MB|mb)', 'memory_usage_mb')
        ]
        
        for pattern, metric_name in time_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            for match in matches:
                try:
                    value = float(match)
                    self.performance_metrics[metric_name].append(value)
                    # 只保留最近1000个值
                    if len(self.performance_metrics[metric_name]) > 1000:
                        self.performance_metrics[metric_name] = self.performance_metrics[metric_name][-1000:]
                except ValueError:
                    continue
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """获取错误摘要"""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            recent_errors = []
            recent_warnings = []
            
            for entry in self.log_entries:
                if entry.timestamp >= cutoff_time:
                    if entry.level == 'ERROR' or entry.level == 'CRITICAL':
                        recent_errors.append(entry)
                    elif entry.level == 'WARNING':
                        recent_warnings.append(entry)
            
            return {
                'period_hours': hours,
                'total_errors': len(recent_errors),
                'total_warnings': len(recent_warnings),
                'top_error_patterns': dict(sorted(self.error_patterns.items(), 
                                                key=lambda x: x[1], reverse=True)[:10]),
                'top_warning_patterns': dict(sorted(self.warning_patterns.items(), 
                                                  key=lambda x: x[1], reverse=True)[:10]),
                'recent_critical_errors': [entry.to_dict() for entry in recent_errors 
                                         if entry.level == 'CRITICAL'][-5:]
            }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        with self._lock:
            summary = {}
            
            for metric_name, values in self.performance_metrics.items():
                if values:
                    summary[metric_name] = {
                        'count': len(values),
                        'average': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values),
                        'recent_average': sum(values[-100:]) / len(values[-100:]) if len(values) >= 100 else sum(values) / len(values)
                    }
            
            return summary
    
    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """检测异常"""
        anomalies = []
        
        with self._lock:
            # 检测错误率异常
            recent_hour = datetime.now() - timedelta(hours=1)
            recent_errors = [e for e in self.log_entries 
                           if e.timestamp >= recent_hour and e.level in ['ERROR', 'CRITICAL']]
            
            if len(recent_errors) > 10:  # 1小时内超过10个错误
                anomalies.append({
                    'type': 'high_error_rate',
                    'severity': 'warning',
                    'message': f'过去1小时内发生了{len(recent_errors)}个错误',
                    'details': {'error_count': len(recent_errors)}
                })
            
            # 检测性能异常
            for metric_name, values in self.performance_metrics.items():
                if len(values) >= 10:
                    recent_values = values[-10:]
                    historical_avg = sum(values[:-10]) / len(values[:-10]) if len(values) > 10 else 0
                    recent_avg = sum(recent_values) / len(recent_values)
                    
                    # 如果最近的平均值比历史平均值高50%以上
                    if historical_avg > 0 and recent_avg > historical_avg * 1.5:
                        anomalies.append({
                            'type': 'performance_degradation',
                            'severity': 'warning',
                            'message': f'{metric_name} 性能下降，当前平均值 {recent_avg:.2f} 比历史平均值 {historical_avg:.2f} 高 {((recent_avg/historical_avg-1)*100):.1f}%',
                            'details': {
                                'metric': metric_name,
                                'current_avg': recent_avg,
                                'historical_avg': historical_avg
                            }
                        })
        
        return anomalies


class LogOptimizer:
    """日志优化器主类"""
    
    def __init__(self, log_dir: str = "logs", 
                 max_file_size: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5,
                 json_format: bool = False,
                 async_logging: bool = True):
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.json_format = json_format
        self.async_logging = async_logging
        
        # 组件
        self.analyzer = LogAnalyzer()
        self.sensitive_filter = SensitiveDataFilter()
        
        # 处理器和格式化器
        self.handlers: List[logging.Handler] = []
        self.loggers: Dict[str, logging.Logger] = {}
        
        # 性能监控
        self.performance_stats = {
            'logs_processed': 0,
            'errors_filtered': 0,
            'start_time': time.time()
        }
        
        # 清理状态
        self._is_cleaned_up = False
        
        # 设置根日志记录器
        self._setup_root_logger()
    
    def _setup_root_logger(self):
        """设置根日志记录器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 创建文件处理器
        file_handler = self._create_file_handler('app.log')
        
        # 创建控制台处理器
        console_handler = self._create_console_handler()
        
        # 创建错误文件处理器
        error_handler = self._create_file_handler('error.log', logging.ERROR)
        
        # 添加处理器
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        root_logger.addHandler(error_handler)
        
        self.handlers.extend([file_handler, console_handler, error_handler])
    
    def _create_file_handler(self, filename: str, level: int = logging.DEBUG) -> logging.Handler:
        """创建文件处理器"""
        file_path = self.log_dir / filename
        
        # 创建轮转文件处理器
        base_handler = logging.handlers.RotatingFileHandler(
            file_path,
            maxBytes=self.max_file_size,
            backupCount=self.backup_count,
            encoding='utf-8'
        )
        base_handler.setLevel(level)
        
        # 设置格式化器
        formatter = StructuredFormatter(
            include_extra=True,
            json_format=self.json_format
        )
        base_handler.setFormatter(formatter)
        
        # 如果启用异步日志，包装为异步处理器
        if self.async_logging:
            handler = AsyncLogHandler(base_handler)
        else:
            handler = base_handler
        
        # 添加分析处理器
        handler.addFilter(self._create_analysis_filter())
        
        return handler
    
    def _create_console_handler(self) -> logging.Handler:
        """创建控制台处理器"""
        base_handler = logging.StreamHandler(sys.stdout)
        base_handler.setLevel(logging.INFO)
        
        # 设置简化的格式化器
        formatter = StructuredFormatter(
            include_extra=False,
            json_format=False
        )
        base_handler.setFormatter(formatter)
        
        # 如果启用异步日志，包装为异步处理器
        if self.async_logging:
            handler = AsyncLogHandler(base_handler)
        else:
            handler = base_handler
        
        return handler
    
    def _create_analysis_filter(self):
        """创建分析过滤器"""
        def analysis_filter(record):
            # 添加到分析器
            self.analyzer.add_log_entry(record)
            
            # 更新性能统计
            self.performance_stats['logs_processed'] += 1
            
            return True
        
        return analysis_filter
    
    def get_logger(self, name: str, level: int = logging.INFO) -> logging.Logger:
        """获取或创建日志记录器"""
        if name in self.loggers:
            return self.loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # 防止重复处理
        logger.propagate = True
        
        self.loggers[name] = logger
        return logger
    
    def set_log_level(self, logger_name: str, level: int):
        """设置日志级别"""
        if logger_name in self.loggers:
            self.loggers[logger_name].setLevel(level)
        else:
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)
    
    def add_sensitive_pattern(self, name: str, pattern: str, replacement: str = '***FILTERED***'):
        """添加敏感信息过滤模式"""
        self.sensitive_filter.add_pattern(name, pattern, replacement)
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """获取日志统计信息"""
        uptime = time.time() - self.performance_stats['start_time']
        
        return {
            'uptime_seconds': uptime,
            'logs_processed': self.performance_stats['logs_processed'],
            'logs_per_second': self.performance_stats['logs_processed'] / uptime if uptime > 0 else 0,
            'error_summary': self.analyzer.get_error_summary(),
            'performance_summary': self.analyzer.get_performance_summary(),
            'anomalies': self.analyzer.detect_anomalies()
        }
    
    def generate_log_report(self, hours: int = 24) -> Dict[str, Any]:
        """生成日志报告"""
        return {
            'report_period_hours': hours,
            'generated_at': datetime.now().isoformat(),
            'statistics': self.get_log_statistics(),
            'error_analysis': self.analyzer.get_error_summary(hours),
            'performance_analysis': self.analyzer.get_performance_summary(),
            'detected_anomalies': self.analyzer.detect_anomalies()
        }
    
    def cleanup_old_logs(self, days: int = 30):
        """清理旧日志文件"""
        cutoff_time = datetime.now() - timedelta(days=days)
        cleaned_count = 0
        
        for log_file in self.log_dir.glob('*.log*'):
            try:
                if log_file.stat().st_mtime < cutoff_time.timestamp():
                    log_file.unlink()
                    cleaned_count += 1
            except Exception as e:
                logging.error(f"清理日志文件 {log_file} 时出错: {str(e)}")
        
        logging.info(f"清理了 {cleaned_count} 个旧日志文件")
    
    def export_logs(self, output_file: str, hours: int = 24, 
                   level: Optional[str] = None) -> bool:
        """导出日志"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                for entry in self.analyzer.log_entries:
                    if entry.timestamp >= cutoff_time:
                        if level is None or entry.level == level:
                            f.write(entry.to_json() + '\n')
            
            logging.info(f"日志已导出到: {output_file}")
            return True
        
        except Exception as e:
            logging.error(f"导出日志时出错: {str(e)}")
            return False
    
    def cleanup(self):
        """清理资源"""
        if self._is_cleaned_up:
            return
        
        logging.info("开始清理LogOptimizer资源...")
        
        try:
            # 关闭所有处理器
            for handler in self.handlers:
                try:
                    handler.close()
                except Exception as e:
                    print(f"关闭日志处理器时出错: {e}", file=sys.stderr)
            
            # 清理处理器列表
            self.handlers.clear()
            
            # 清理日志记录器
            for logger in self.loggers.values():
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)
            
            self.loggers.clear()
            
            self._is_cleaned_up = True
            logging.info("LogOptimizer资源清理完成")
        
        except Exception as e:
            print(f"清理LogOptimizer资源时出错: {e}", file=sys.stderr)


# 全局日志优化器实例
_global_optimizer: Optional[LogOptimizer] = None


def setup_global_optimizer(log_dir: str = "logs",
                          max_file_size: int = 10 * 1024 * 1024,
                          backup_count: int = 5,
                          json_format: bool = False,
                          async_logging: bool = True) -> LogOptimizer:
    """设置全局日志优化器"""
    global _global_optimizer
    
    if _global_optimizer:
        _global_optimizer.cleanup()
    
    _global_optimizer = LogOptimizer(
        log_dir=log_dir,
        max_file_size=max_file_size,
        backup_count=backup_count,
        json_format=json_format,
        async_logging=async_logging
    )
    
    return _global_optimizer


def get_global_optimizer() -> Optional[LogOptimizer]:
    """获取全局日志优化器"""
    return _global_optimizer


def cleanup_global_optimizer():
    """清理全局日志优化器"""
    global _global_optimizer
    
    if _global_optimizer:
        _global_optimizer.cleanup()
        _global_optimizer = None


def get_optimized_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """获取优化的日志记录器"""
    if _global_optimizer:
        return _global_optimizer.get_logger(name, level)
    else:
        # 如果没有全局优化器，返回标准日志记录器
        return logging.getLogger(name)