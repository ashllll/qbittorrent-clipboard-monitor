"""
结构化日志系统

提供功能完善的日志管理，包括：
- JSON 结构化日志输出
- 日志文件轮转（按大小和时间）
- 彩色控制台输出
- 多目标日志级别路由
- 敏感信息过滤集成
"""

import json
import logging
import logging.handlers
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Union, TextIO
from dataclasses import dataclass, field, asdict
from enum import Enum

from .logging_filters import SensitiveDataFilter


class LogFormat(str, Enum):
    """日志格式类型"""
    TEXT = "text"           # 普通文本格式
    JSON = "json"           # JSON 结构化格式
    DETAILED = "detailed"   # 详细文本格式（包含更多上下文）


@dataclass
class LogConfig:
    """日志配置数据类
    
    Attributes:
        level: 全局日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        format: 日志格式类型 (text/json/detailed)
        console_enabled: 是否启用控制台输出
        console_color: 是否启用彩色控制台输出
        file_enabled: 是否启用文件日志
        file_path: 日志文件路径
        file_max_bytes: 单个日志文件最大大小（字节）
        file_backup_count: 保留的备份文件数量
        file_max_age_days: 日志文件最大保留天数
        separate_levels: 是否按日志级别分离到不同文件
        debug_separate: 是否将 DEBUG 日志单独输出
    """
    level: str = "INFO"
    format: str = "text"
    console_enabled: bool = True
    console_color: bool = True
    file_enabled: bool = True
    file_path: str = "logs/qb-monitor.log"
    file_max_bytes: int = 10 * 1024 * 1024  # 10MB
    file_backup_count: int = 5
    file_max_age_days: int = 7
    separate_levels: bool = False
    debug_separate: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogConfig":
        """从字典创建配置"""
        # 过滤掉不支持的字段
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)


# 日志级别颜色映射
LEVEL_COLORS = {
    "DEBUG": "\033[36m",      # 青色
    "INFO": "\033[32m",       # 绿色
    "WARNING": "\033[33m",    # 黄色
    "ERROR": "\033[31m",      # 红色
    "CRITICAL": "\033[35m",   # 紫色
    "RESET": "\033[0m",       # 重置
}

# 粗体样式
BOLD = "\033[1m"
RESET = "\033[0m"


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        use_color: bool = True
    ):
        super().__init__(fmt, datefmt)
        self.use_color = use_color and sys.platform != "win32" or self._supports_color()
    
    def _supports_color(self) -> bool:
        """检查终端是否支持颜色"""
        if sys.platform == "win32":
            return os.getenv("ANSICON") is not None or os.getenv("TERM") is not None
        return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        if not self.use_color:
            return super().format(record)
        
        # 保存原始值
        levelname = record.levelname
        
        # 添加颜色
        color = LEVEL_COLORS.get(levelname, LEVEL_COLORS["RESET"])
        record.levelname = f"{color}{BOLD}{levelname}{RESET}{LEVEL_COLORS['RESET']}"
        
        # 高亮重要日志的消息
        if record.levelno >= logging.WARNING:
            record.msg = f"{color}{record.msg}{LEVEL_COLORS['RESET']}"
        
        result = super().format(record)
        
        # 恢复原始值
        record.levelname = levelname
        
        return result


class JsonFormatter(logging.Formatter):
    """JSON 结构化日志格式化器"""
    
    def __init__(
        self,
        include_extra: bool = True,
        include_stack_info: bool = False
    ):
        super().__init__()
        self.include_extra = include_extra
        self.include_stack_info = include_stack_info
        self._hostname = os.uname().nodename if hasattr(os, "uname") else "unknown"
        self._project_name = "qb-monitor"
    
    def format(self, record: logging.LogRecord) -> str:
        """将日志记录格式化为 JSON"""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "source": {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            },
            "host": self._hostname,
            "project": self._project_name,
        }
        
        # 添加线程和进程信息
        if hasattr(record, "thread"):
            log_data["thread"] = record.thread
        if hasattr(record, "process"):
            log_data["process"] = record.process
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
            }
            if self.include_stack_info:
                log_data["exception"]["traceback"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if self.include_extra:
            # 获取所有非标准字段
            standard_attrs = {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "getMessage"
            }
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in standard_attrs and not key.startswith("_"):
                    extra_fields[key] = value
            
            if extra_fields:
                log_data["extra"] = extra_fields
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class DetailedFormatter(logging.Formatter):
    """详细日志格式化器（用于调试）"""
    
    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None
    ):
        super().__init__(fmt or self._default_fmt(), datefmt or "%Y-%m-%d %H:%M:%S.%f")
    
    def _default_fmt(self) -> str:
        return (
            "%(asctime)s [%(levelname)s] %(name)s\n"
            "  File: %(pathname)s:%(lineno)d (in %(funcName)s)\n"
            "  Message: %(message)s"
        )
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录，添加额外上下文"""
        # 添加相对时间
        if hasattr(record, "relativeCreated"):
            record.relative_secs = record.relativeCreated / 1000
        
        result = super().format(record)
        
        # 添加异常信息
        if record.exc_info:
            result += "\n  Exception:\n"
            result += "    " + self.formatException(record.exc_info).replace("\n", "\n    ")
        
        return result


class TimeAndSizeRotatingHandler(logging.handlers.RotatingFileHandler):
    """同时支持时间和大小轮转的日志处理器"""
    
    def __init__(
        self,
        filename: Union[str, Path],
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        max_age_days: int = 7,
        encoding: str = "utf-8",
        delay: bool = False
    ):
        super().__init__(
            filename=str(filename),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding,
            delay=delay
        )
        self.max_age_days = max_age_days
        self.base_filename = Path(filename)
        self._cleanup_old_logs()
    
    def doRollover(self):
        """执行日志轮转"""
        super().doRollover()
        self._cleanup_old_logs()
    
    def _cleanup_old_logs(self):
        """清理超过保留期限的旧日志文件"""
        if not self.base_filename.parent.exists():
            return
        
        cutoff_time = datetime.now() - timedelta(days=self.max_age_days)
        pattern = self.base_filename.name + ".*"
        
        for log_file in self.base_filename.parent.glob(pattern):
            try:
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_time:
                    log_file.unlink()
            except (OSError, PermissionError):
                pass


class StructuredLogger:
    """结构化日志记录器
    
    提供高级日志功能的包装类。
    """
    
    def __init__(self, name: str):
        self.name = name
        self._logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}
    
    def bind(self, **kwargs) -> "StructuredLogger":
        """绑定上下文信息"""
        new_logger = StructuredLogger(self.name)
        new_logger._context = {**self._context, **kwargs}
        return new_logger
    
    def _log(
        self,
        level: int,
        msg: str,
        *args,
        exc_info=None,
        extra: Optional[Dict] = None,
        **kwargs
    ):
        """内部日志方法"""
        # 合并上下文
        merged_extra = {**self._context, **(extra or {})}
        if kwargs:
            merged_extra.update(kwargs)
        
        self._logger.log(
            level,
            msg,
            *args,
            exc_info=exc_info,
            extra=merged_extra if merged_extra else None
        )
    
    def debug(self, msg: str, *args, **kwargs):
        """记录 DEBUG 级别日志"""
        self._log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        """记录 INFO 级别日志"""
        self._log(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """记录 WARNING 级别日志"""
        self._log(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        """记录 ERROR 级别日志"""
        self._log(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        """记录 CRITICAL 级别日志"""
        self._log(logging.CRITICAL, msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, exc_info=True, **kwargs):
        """记录异常信息"""
        self._log(logging.ERROR, msg, *args, exc_info=exc_info, **kwargs)


def create_formatter(
    format_type: LogFormat,
    use_color: bool = False
) -> logging.Formatter:
    """创建日志格式化器
    
    Args:
        format_type: 日志格式类型
        use_color: 是否使用彩色输出
        
    Returns:
        配置好的格式化器
    """
    if format_type == LogFormat.JSON:
        return JsonFormatter()
    elif format_type == LogFormat.DETAILED:
        return DetailedFormatter()
    else:  # TEXT
        if use_color:
            return ColoredFormatter(
                fmt="%(asctime)s %(levelname)s %(name)s - %(message)s",
                datefmt="%H:%M:%S",
                use_color=True
            )
        else:
            return logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )


def setup_logging(config: Optional[LogConfig] = None) -> logging.Logger:
    """设置结构化日志系统
    
    Args:
        config: 日志配置，如果为 None 则使用默认配置
        
    Returns:
        配置好的根日志记录器
    """
    if config is None:
        config = LogConfig()
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level.upper()))
    
    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 创建敏感信息过滤器
    sensitive_filter = SensitiveDataFilter()
    
    # 解析格式类型
    try:
        format_type = LogFormat(config.format.lower())
    except ValueError:
        format_type = LogFormat.TEXT
    
    # 配置控制台处理器
    if config.console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.level.upper()))
        
        # 使用彩色格式化器（如果是文本格式且启用颜色）
        use_color = config.console_color and format_type == LogFormat.TEXT
        console_formatter = create_formatter(
            LogFormat.TEXT if use_color else format_type,
            use_color=use_color
        )
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(sensitive_filter)
        root_logger.addHandler(console_handler)
    
    # 配置文件处理器
    if config.file_enabled and config.file_path:
        log_path = Path(config.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 主日志文件处理器
        file_handler = TimeAndSizeRotatingHandler(
            filename=log_path,
            max_bytes=config.file_max_bytes,
            backup_count=config.file_backup_count,
            max_age_days=config.file_max_age_days,
            encoding="utf-8"
        )
        file_handler.setLevel(getattr(logging, config.level.upper()))
        
        # 文件使用 JSON 或文本格式（不使用颜色）
        file_formatter = create_formatter(format_type, use_color=False)
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(sensitive_filter)
        root_logger.addHandler(file_handler)
        
        # 分离 DEBUG 日志
        if config.debug_separate and config.level.upper() == "DEBUG":
            debug_path = log_path.parent / f"{log_path.stem}.debug{log_path.suffix}"
            debug_handler = TimeAndSizeRotatingHandler(
                filename=debug_path,
                max_bytes=config.file_max_bytes,
                backup_count=config.file_backup_count,
                max_age_days=config.file_max_age_days,
                encoding="utf-8"
            )
            debug_handler.setLevel(logging.DEBUG)
            debug_handler.setFormatter(file_formatter)
            debug_handler.addFilter(sensitive_filter)
            root_logger.addHandler(debug_handler)
        
        # 分离错误日志
        if config.separate_levels:
            error_path = log_path.parent / f"{log_path.stem}.error{log_path.suffix}"
            error_handler = TimeAndSizeRotatingHandler(
                filename=error_path,
                max_bytes=config.file_max_bytes,
                backup_count=config.file_backup_count,
                max_age_days=config.file_max_age_days,
                encoding="utf-8"
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(file_formatter)
            error_handler.addFilter(sensitive_filter)
            root_logger.addHandler(error_handler)
    
    return root_logger


def get_logger(name: str) -> StructuredLogger:
    """获取结构化日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        结构化日志记录器
    """
    return StructuredLogger(name)


def configure_from_dict(config_dict: Dict[str, Any]) -> logging.Logger:
    """从字典配置日志系统
    
    Args:
        config_dict: 配置字典，应包含日志配置
        
    Returns:
        配置好的根日志记录器
    """
    log_config = LogConfig.from_dict(config_dict.get("logging", {}))
    return setup_logging(log_config)


def configure_from_config(config) -> logging.Logger:
    """从应用配置对象配置日志系统
    
    Args:
        config: 应用配置对象，需要包含 log_level 属性
        
    Returns:
        配置好的根日志记录器
    """
    # 从配置中提取日志配置
    log_dict = {}
    
    # 尝试获取嵌套的日志配置
    if hasattr(config, "logging") and isinstance(config.logging, dict):
        log_dict = config.logging
    elif hasattr(config, "to_dict"):
        config_dict = config.to_dict()
        log_dict = config_dict.get("logging", {})
    
    # 设置日志级别（从顶层配置获取）
    if hasattr(config, "log_level"):
        log_dict["level"] = config.log_level
    
    log_config = LogConfig.from_dict(log_dict)
    return setup_logging(log_config)


# 兼容旧版的便捷函数
def setup_sensitive_logging(
    level: str = "INFO",
    logger_name: Optional[str] = None
) -> logging.Logger:
    """设置带有敏感信息过滤的日志记录器（兼容旧版）
    
    Args:
        level: 日志级别
        logger_name: 日志记录器名称
        
    Returns:
        配置好的日志记录器
    """
    config = LogConfig(
        level=level,
        format="text",
        console_enabled=True,
        console_color=True,
        file_enabled=False
    )
    
    setup_logging(config)
    return logging.getLogger(logger_name)
