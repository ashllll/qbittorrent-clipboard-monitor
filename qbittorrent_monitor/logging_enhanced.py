"""
增强的日志配置模块

提供结构化日志、错误上下文、日志过滤、日志轮转等功能。
"""

import json
import logging
import logging.config
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
import time
from collections import defaultdict


class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogContext:
    """日志上下文"""
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    operation: Optional[str] = None
    resource_id: Optional[str] = None
    correlation_id: Optional[str] = None
    duration_ms: Optional[float] = None
    custom_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnhancedLogRecord:
    """增强的日志记录"""
    timestamp: str
    level: str
    logger: str
    message: str
    module: str
    function: str
    line_number: int
    thread_id: int
    process_id: int
    context: Optional[Dict[str, Any]] = None
    exception_info: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None
    performance_metrics: Optional[Dict[str, float]] = None


class ContextFilter(logging.Filter):
    """上下文过滤器"""
    
    def __init__(self, context: Optional[LogContext] = None):
        super().__init__()
        self.context = context or LogContext()
        self._local = threading.local()
    
    def set_context(self, context: LogContext):
        """设置日志上下文"""
        self.context = context
    
    def get_context(self) -> LogContext:
        """获取日志上下文"""
        return getattr(self._local, 'context', self.context)
    
    def filter(self, record):
        """过滤日志记录"""
        # 将上下文附加到日志记录
        context = self.get_context()
        if context:
            record.context = asdict(context)
        
        return True


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def __init__(
        self,
        format_type: str = "json",
        include_fields: Optional[List[str]] = None,
        exclude_fields: Optional[List[str]] = None,
        date_format: str = "%Y-%m-%dT%H:%M:%S.%fZ"
    ):
        super().__init__()
        self.format_type = format_type
        self.include_fields = include_fields or []
        self.exclude_fields = exclude_fields or [
            'pathname', 'lineno', 'msecs', 'relativeCreated', 'levelno', 'exc_info', 'exc_text', 'message'
        ]
        self.date_format = date_format
    
    def format(self, record):
        """格式化日志记录"""
        if self.format_type == "json":
            return self._format_json(record)
        else:
            return self._format_plain(record)
    
    def _format_json(self, record):
        """JSON格式化"""
        # 构建基础日志记录
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).strftime(self.date_format),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line_number": record.lineno,
            "thread_id": record.thread,
            "process_id": record.process,
        }
        
        # 添加上下文信息
        if hasattr(record, 'context') and record.context:
            log_data["context"] = record.context
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self._format_exception(record.exc_info)
        
        # 添加性能指标
        if hasattr(record, 'performance_metrics') and record.performance_metrics:
            log_data["performance"] = record.performance_metrics
        
        # 添加自定义字段
        for key, value in record.__dict__.items():
            if key not in self.exclude_fields and not key.startswith('_'):
                if not self.include_fields or key in self.include_fields:
                    log_data[key] = value
        
        # 过滤空值
        log_data = {k: v for k, v in log_data.items() if v is not None}
        
        return json.dumps(log_data, ensure_ascii=False, default=str)
    
    def _format_plain(self, record):
        """纯文本格式化"""
        # 构建格式化的日志消息
        timestamp = datetime.fromtimestamp(record.created).strftime(self.date_format)
        
        # 基础信息
        parts = [
            f"[{timestamp}]",
            f"[{record.levelname}]",
            f"[{record.name}]",
            record.getMessage()
        ]
        
        # 添加上下文信息
        if hasattr(record, 'context') and record.context:
            context_parts = []
            for key, value in record.context.items():
                context_parts.append(f"{key}={value}")
            
            if context_parts:
                parts.append(f"[{', '.join(context_parts)}]")
        
        # 添加位置信息
        parts.append(f"({record.module}:{record.function}:{record.lineno})")
        
        return " ".join(parts)
    
    def _format_exception(self, exc_info):
        """格式化异常信息"""
        exc_type, exc_value, exc_traceback = exc_info
        
        return {
            "type": exc_type.__name__,
            "message": str(exc_value),
            "traceback": traceback.format_exception(exc_type, exc_value, exc_traceback)
        }


class PerformanceFilter(logging.Filter):
    """性能过滤器和指标收集器"""
    
    def __init__(self):
        super().__init__()
        self.performance_data = defaultdict(list)
        self._lock = threading.Lock()
    
    def filter(self, record):
        """过滤并收集性能数据"""
        # 如果记录包含性能指标，收集起来
        if hasattr(record, 'performance_metrics') and record.performance_metrics:
            with self._lock:
                for metric_name, value in record.performance_metrics.items():
                    self.performance_data[metric_name].append({
                        'value': value,
                        'timestamp': record.created,
                        'logger': record.name,
                        'level': record.levelname
                    })
        
        return True
    
    def get_performance_summary(self, metric_name: Optional[str] = None) -> Dict[str, Any]:
        """获取性能摘要"""
        with self._lock:
            if metric_name:
                data = self.performance_data.get(metric_name, [])
            else:
                data = self.performance_data
            
            summary = {}
            for name, values in data.items():
                if not values:
                    continue
                
                numeric_values = [v['value'] for v in values if isinstance(v['value'], (int, float))]
                if not numeric_values:
                    continue
                
                summary[name] = {
                    'count': len(numeric_values),
                    'min': min(numeric_values),
                    'max': max(numeric_values),
                    'avg': sum(numeric_values) / len(numeric_values),
                    'latest': numeric_values[-1] if numeric_values else None,
                    'latest_timestamp': values[-1]['timestamp'] if values else None
                }
            
            return summary


class ErrorContextFilter(logging.Filter):
    """错误上下文过滤器"""
    
    def __init__(self):
        super().__init__()
        self.error_count = defaultdict(int)
        self.last_error_time = defaultdict(float)
        self._lock = threading.Lock()
    
    def filter(self, record):
        """过滤并添加错误上下文"""
        if record.levelno >= logging.ERROR:
            with self._lock:
                error_key = f"{record.name}:{record.module}:{record.funcName}"
                self.error_count[error_key] += 1
                self.last_error_time[error_key] = record.created
                
                # 添加错误统计到记录
                record.error_count = self.error_count[error_key]
                record.error_rate = self._calculate_error_rate(error_key)
                record.time_since_last_error = record.created - self.last_error_time[error_key]
        
        return True
    
    def _calculate_error_rate(self, error_key: str) -> float:
        """计算错误率（每分钟错误数）"""
        with self._lock:
            now = time.time()
            # 简化实现：假设每分钟一个时间窗口
            # 实际实现中可以维护滑动窗口
            return min(self.error_count[error_key], 60.0) / 60.0


class EnhancedLoggerAdapter(logging.LoggerAdapter):
    """增强的日志适配器，支持上下文"""
    
    def __init__(self, logger: logging.Logger, context: Optional[LogContext] = None):
        super().__init__(logger, asdict(context) if context else {})
        self.context = context or LogContext()
    
    def process(self, msg, kwargs):
        """处理日志消息，添加上下文"""
        # 合并上下文
        merged_context = {**asdict(self.context), **self.extra}
        
        # 添加到kwargs
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        
        kwargs['extra']['context'] = merged_context
        
        return msg, kwargs
    
    def set_context(self, **kwargs):
        """设置上下文"""
        self.context.custom_fields.update(kwargs)
    
    def set_operation(self, operation: str):
        """设置操作"""
        self.context.operation = operation
    
    def set_correlation_id(self, correlation_id: str):
        """设置关联ID"""
        self.context.correlation_id = correlation_id
    
    def log_performance(self, level: int, message: str, **metrics):
        """记录性能指标"""
        extra = {
            'performance_metrics': metrics
        }
        self.log(level, message, extra=extra)


class LogManager:
    """日志管理器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._get_default_config()
        self._loggers = {}
        self._context_filter = ContextFilter()
        self._performance_filter = PerformanceFilter()
        self._error_filter = ErrorContextFilter()
        self._setup_logging()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "structured": {
                    "()": "qbittorrent_monitor.logging_enhanced.StructuredFormatter",
                    "format_type": "json",
                    "include_fields": ["timestamp", "level", "logger", "message", "context"]
                },
                "plain": {
                    "()": "qbittorrent_monitor.logging_enhanced.StructuredFormatter",
                    "format_type": "plain"
                },
                "detailed": {
                    "()": "qbittorrent_monitor.logging_enhanced.StructuredFormatter",
                    "format_type": "plain",
                    "include_fields": ["timestamp", "level", "logger", "message", "context", "module", "function", "line_number"]
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "INFO",
                    "formatter": "plain",
                    "stream": "ext://sys.stdout"
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "DEBUG",
                    "formatter": "structured",
                    "filename": "logs/qbittorrent_monitor.log",
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": 5,
                    "encoding": "utf-8"
                },
                "error_file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "ERROR",
                    "formatter": "detailed",
                    "filename": "logs/errors.log",
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": 5,
                    "encoding": "utf-8"
                }
            },
            "loggers": {
                "qbittorrent_monitor": {
                    "level": "DEBUG",
                    "handlers": ["console", "file", "error_file"],
                    "propagate": False
                }
            },
            "root": {
                "level": "INFO",
                "handlers": ["console"]
            }
        }
    
    def _setup_logging(self):
        """设置日志系统"""
        # 确保日志目录存在
        for handler_config in self.config.get("handlers", {}).values():
            filename = handler_config.get("filename")
            if filename:
                log_dir = Path(filename).parent
                log_dir.mkdir(parents=True, exist_ok=True)
        
        # 配置日志系统
        logging.config.dictConfig(self.config)
        
        # 添加过滤器到根日志记录器
        root_logger = logging.getLogger()
        root_logger.addFilter(self._context_filter)
        root_logger.addFilter(self._performance_filter)
        root_logger.addFilter(self._error_filter)
        
        self.logger = logging.getLogger("qbittorrent_monitor")
        self.logger.info("增强日志系统已初始化")
    
    def get_logger(self, name: str) -> EnhancedLoggerAdapter:
        """获取增强日志记录器"""
        if name not in self._loggers:
            base_logger = logging.getLogger(name)
            self._loggers[name] = EnhancedLoggerAdapter(base_logger)
        
        return self._loggers[name]
    
    def set_global_context(self, context: LogContext):
        """设置全局日志上下文"""
        self._context_filter.set_context(context)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        return self._performance_filter.get_performance_summary()
    
    def get_error_summary(self) -> Dict[str, Any]:
        """获取错误摘要"""
        with self._error_filter._lock:
            return {
                "error_count": dict(self._error_filter.error_count),
                "last_error_time": {
                    k: datetime.fromtimestamp(v).isoformat() 
                    for k, v in self._error_filter.last_error_time.items()
                }
            }
    
    def create_logger(self, name: str, level: LogLevel = LogLevel.INFO, 
                     context: Optional[LogContext] = None) -> EnhancedLoggerAdapter:
        """创建新的增强日志记录器"""
        logger = self.get_logger(name)
        logger.setLevel(level.value)
        
        if context:
            logger.context = context
        
        return logger


# 全局日志管理器实例
_log_manager = None

def get_log_manager() -> LogManager:
    """获取全局日志管理器"""
    global _log_manager
    if _log_manager is None:
        _log_manager = LogManager()
    return _log_manager

def setup_enhanced_logging(config: Optional[Dict[str, Any]] = None) -> LogManager:
    """设置增强日志系统"""
    global _log_manager
    _log_manager = LogManager(config)
    return _log_manager

def get_enhanced_logger(name: str) -> EnhancedLoggerAdapter:
    """获取增强日志记录器"""
    return get_log_manager().get_logger(name)

def log_with_context(level: int, message: str, **context):
    """带上下文的日志记录"""
    logger = get_enhanced_logger(__name__)
    logger.set_context(**context)
    logger.log(level, message)

def log_performance(level: int, message: str, **metrics):
    """记录性能指标"""
    logger = get_enhanced_logger(__name__)
    logger.log_performance(level, message, **metrics)

# 便捷函数
def debug(message: str, **context):
    """调试日志"""
    log_with_context(logging.DEBUG, message, **context)

def info(message: str, **context):
    """信息日志"""
    log_with_context(logging.INFO, message, **context)

def warning(message: str, **context):
    """警告日志"""
    log_with_context(logging.WARNING, message, **context)

def error(message: str, exception: Optional[Exception] = None, **context):
    """错误日志"""
    logger = get_enhanced_logger(__name__)
    logger.set_context(**context)
    
    if exception:
        logger.error(message, exc_info=True)
    else:
        logger.error(message)

def critical(message: str, exception: Optional[Exception] = None, **context):
    """严重错误日志"""
    logger = get_enhanced_logger(__name__)
    logger.set_context(**context)
    
    if exception:
        logger.critical(message, exc_info=True)
    else:
        logger.critical(message)

