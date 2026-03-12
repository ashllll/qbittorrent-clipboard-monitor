"""全局异常处理器

提供统一的异常处理、日志记录和错误转换功能。

使用示例:
    # 使用上下文管理器
    from qbittorrent_monitor.exception_handler import exception_context
    
    with exception_context(NetworkError, "连接失败"):
        response = await session.get(url)
    
    # 使用装饰器
    from qbittorrent_monitor.exception_handler import handle_exceptions
    
    @handle_exceptions(NetworkError, default_return=None, log_level=logging.WARNING)
    async def fetch_data():
        return await api.get_data()
    
    # 使用全局异常处理器
    from qbittorrent_monitor.exception_handler import GlobalExceptionHandler
    
    GlobalExceptionHandler.register(NetworkError, lambda e: logger.warning(f"网络错误: {e}"))
"""

from __future__ import annotations

import asyncio
import functools
import logging
from contextlib import contextmanager
from typing import Any, Callable, Optional, Type, TypeVar, Union

from .exceptions_unified import (
    QBittorrentMonitorError,
    ErrorSeverity,
    RetryableError,
    NonRetryableError,
)

logger = logging.getLogger(__name__)
T = TypeVar('T')


# =============================================================================
# 全局异常处理器
# =============================================================================

class GlobalExceptionHandler:
    """全局异常处理器
    
    提供统一的异常处理、日志记录和错误转换功能。
    
    类属性:
        _handlers: 注册的异常处理器字典
        _default_handler: 默认处理器
    
    示例:
        # 注册特定异常类型的处理器
        GlobalExceptionHandler.register(NetworkError, handle_network_error)
        
        # 设置默认处理器
        GlobalExceptionHandler.set_default(handle_unknown_error)
        
        # 处理异常
        try:
            risky_operation()
        except Exception as e:
            GlobalExceptionHandler.handle(e)
    """
    
    _handlers: dict[type[Exception], Callable[[Exception], Any]] = {}
    _default_handler: Optional[Callable[[Exception], Any]] = None
    _logger = logging.getLogger(__name__)
    
    @classmethod
    def register(
        cls,
        exc_type: type[Exception],
        handler: Callable[[Exception], Any]
    ) -> None:
        """注册特定异常类型的处理器
        
        Args:
            exc_type: 异常类型
            handler: 处理函数，接收异常实例作为参数
        """
        cls._handlers[exc_type] = handler
        cls._logger.debug(f"已注册异常处理器: {exc_type.__name__}")
    
    @classmethod
    def unregister(cls, exc_type: type[Exception]) -> bool:
        """注销异常处理器
        
        Args:
            exc_type: 异常类型
            
        Returns:
            是否成功注销
        """
        if exc_type in cls._handlers:
            del cls._handlers[exc_type]
            cls._logger.debug(f"已注销异常处理器: {exc_type.__name__}")
            return True
        return False
    
    @classmethod
    def set_default(cls, handler: Callable[[Exception], Any]) -> None:
        """设置默认处理器
        
        当没有匹配的特定处理器时，使用默认处理器。
        
        Args:
            handler: 默认处理函数
        """
        cls._default_handler = handler
        cls._logger.debug("已设置默认异常处理器")
    
    @classmethod
    def clear(cls) -> None:
        """清除所有注册的处理器"""
        cls._handlers.clear()
        cls._default_handler = None
        cls._logger.debug("已清除所有异常处理器")
    
    @classmethod
    def handle(cls, exc: Exception) -> Any:
        """处理异常
        
        按照以下顺序处理异常：
        1. 查找最匹配的特定处理器（按继承层次）
        2. 如果没有特定处理器，使用默认处理器
        3. 如果没有默认处理器，重新抛出异常
        
        Args:
            exc: 异常实例
            
        Returns:
            处理器的返回值
            
        Raises:
            Exception: 如果没有找到处理器，重新抛出原异常
        """
        # 记录异常
        cls._log_exception(exc)
        
        # 查找最匹配的处理器
        exc_type = type(exc)
        
        # 首先尝试精确匹配
        if exc_type in cls._handlers:
            cls._logger.debug(f"使用精确匹配的处理器: {exc_type.__name__}")
            return cls._handlers[exc_type](exc)
        
        # 然后尝试继承匹配
        for registered_type, handler in cls._handlers.items():
            if isinstance(exc, registered_type):
                cls._logger.debug(
                    f"使用继承匹配的处理器: {exc_type.__name__} -> {registered_type.__name__}"
                )
                return handler(exc)
        
        # 使用默认处理器
        if cls._default_handler:
            cls._logger.debug(f"使用默认处理器处理: {exc_type.__name__}")
            return cls._default_handler(exc)
        
        # 重新抛出
        cls._logger.debug(f"没有匹配的处理器，重新抛出: {exc_type.__name__}")
        raise exc
    
    @classmethod
    def _log_exception(cls, exc: Exception) -> None:
        """记录异常信息
        
        Args:
            exc: 异常实例
        """
        exc_type = type(exc).__name__
        
        # 如果是项目异常，使用其严重程度
        if isinstance(exc, QBittorrentMonitorError):
            severity = exc.severity
            if severity == ErrorSeverity.CRITICAL:
                cls._logger.critical(f"[{exc_type}] {exc}")
            elif severity == ErrorSeverity.ERROR:
                cls._logger.error(f"[{exc_type}] {exc}")
            elif severity == ErrorSeverity.WARNING:
                cls._logger.warning(f"[{exc_type}] {exc}")
            else:
                cls._logger.info(f"[{exc_type}] {exc}")
        else:
            # 普通异常
            cls._logger.error(f"[{exc_type}] {exc}")


# =============================================================================
# 异常处理装饰器
# =============================================================================

def handle_exceptions(
    *exceptions: type[Exception],
    default_return: Any = None,
    log_level: int = logging.ERROR,
    reraise: bool = False,
    on_exception: Optional[Callable[[Exception], None]] = None
) -> Callable:
    """异常处理装饰器
    
    捕获指定异常，记录日志，并返回默认值或重新抛出。
    
    Args:
        exceptions: 要捕获的异常类型
        default_return: 异常时的默认返回值
        log_level: 日志级别
        reraise: 是否重新抛出异常
        on_exception: 异常时的回调函数
        
    Returns:
        装饰器函数
        
    示例:
        @handle_exceptions(NetworkError, default_return=None)
        async def fetch_data():
            return await api.get_data()
        
        @handle_exceptions(Exception, reraise=True, on_exception=report_error)
        def critical_operation():
            return process_data()
    """
    if not exceptions:
        exceptions = (Exception,)
    
    def decorator(func: Callable[..., T]) -> Callable[..., T | Any]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T | Any:
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                logger.log(log_level, f"{func.__name__} 执行失败: {e}")
                
                if on_exception:
                    try:
                        on_exception(e)
                    except Exception as callback_error:
                        logger.warning(f"异常回调失败: {callback_error}")
                
                if reraise:
                    raise
                return default_return
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T | Any:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                logger.log(log_level, f"{func.__name__} 执行失败: {e}")
                
                if on_exception:
                    try:
                        on_exception(e)
                    except Exception as callback_error:
                        logger.warning(f"异常回调失败: {callback_error}")
                
                if reraise:
                    raise
                return default_return
        
        # 根据函数类型返回适当的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def retry_on_exception(
    *exceptions: type[Exception],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> Callable:
    """异常重试装饰器
    
    捕获指定异常并重试，使用指数退避策略。
    
    Args:
        exceptions: 要捕获的异常类型
        max_retries: 最大重试次数
        base_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数基数
        on_retry: 重试时的回调函数，接收异常和重试次数
        
    Returns:
        装饰器函数
        
    示例:
        @retry_on_exception(NetworkError, max_retries=3, base_delay=1.0)
        async def fetch_data():
            return await api.get_data()
    """
    if not exceptions:
        exceptions = (Exception,)
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        # 计算指数退避延迟（添加抖动）
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        # 添加随机抖动 (±20%)
                        jitter = delay * 0.2 * (2 * __import__('random').random() - 1)
                        sleep_time = delay + jitter
                        
                        logger.warning(
                            f"{func.__name__} 第 {attempt + 1}/{max_retries + 1} 次尝试失败，"
                            f"{sleep_time:.2f}秒后重试..."
                        )
                        
                        if on_retry:
                            try:
                                on_retry(e, attempt + 1)
                            except Exception as callback_error:
                                logger.warning(f"重试回调失败: {callback_error}")
                        
                        await asyncio.sleep(sleep_time)
                    else:
                        logger.error(
                            f"{func.__name__} 在 {max_retries + 1} 次尝试后仍然失败"
                        )
            
            # 重试耗尽，抛出异常
            raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        sleep_time = delay
                        
                        logger.warning(
                            f"{func.__name__} 第 {attempt + 1}/{max_retries + 1} 次尝试失败，"
                            f"{sleep_time:.2f}秒后重试..."
                        )
                        
                        if on_retry:
                            try:
                                on_retry(e, attempt + 1)
                            except Exception as callback_error:
                                logger.warning(f"重试回调失败: {callback_error}")
                        
                        import time
                        time.sleep(sleep_time)
                    else:
                        logger.error(
                            f"{func.__name__} 在 {max_retries + 1} 次尝试后仍然失败"
                        )
            
            raise last_exception
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# =============================================================================
# 异常转换工具
# =============================================================================

@contextmanager
def exception_context(
    target_exc: Type[QBittorrentMonitorError],
    message: Optional[str] = None,
    preserve_cause: bool = True,
    **context_kwargs
):
    """异常转换上下文管理器
    
    将捕获的异常转换为目标异常类型，同时保留原始异常链。
    
    Args:
        target_exc: 目标异常类型
        message: 可选的自定义消息
        preserve_cause: 是否保留原始异常原因
        **context_kwargs: 附加到异常的上下文信息
        
    Yields:
        None
        
    Raises:
        target_exc: 转换后的异常
        
    示例:
        with exception_context(NetworkError, "连接失败"):
            response = await session.get(url)
        
        with exception_context(ConfigError, "加载配置失败", file_path=config_path):
            config = yaml.safe_load(content)
    """
    try:
        yield
    except Exception as e:
        # 如果已经是目标类型或子类型，直接抛出
        if isinstance(e, target_exc):
            raise
        
        # 如果已经是项目异常，不转换
        if isinstance(e, QBittorrentMonitorError):
            raise
        
        # 构建消息
        msg = message or str(e)
        
        # 创建新异常
        new_exc = target_exc(msg)
        
        # 添加上下文信息
        for key, value in context_kwargs.items():
            new_exc.add_context(key, value)
        
        # 保留或丢弃原始异常链
        if preserve_cause:
            raise new_exc from e
        else:
            raise new_exc


def wrap_exception(
    exception: Exception,
    target_type: Type[T],
    message: Optional[str] = None,
    **context_kwargs
) -> T:
    """将异常包装为目标类型
    
    Args:
        exception: 原始异常
        target_type: 目标异常类型
        message: 可选的自定义消息
        **context_kwargs: 附加到异常的上下文信息
        
    Returns:
        包装后的异常实例
    """
    msg = message or str(exception)
    wrapped = target_type(msg)
    wrapped.__cause__ = exception
    
    # 添加上下文信息
    for key, value in context_kwargs.items():
        wrapped.add_context(key, value)
    
    return wrapped


def convert_exception(
    source_exc: type[Exception],
    target_exc: Type[QBittorrentMonitorError],
    message: Optional[str] = None
) -> Callable:
    """异常类型转换装饰器
    
    将特定类型的异常转换为项目异常。
    
    Args:
        source_exc: 源异常类型
        target_exc: 目标异常类型
        message: 可选的自定义消息
        
    Returns:
        装饰器函数
        
    示例:
        @convert_exception(requests.RequestException, NetworkError, "API请求失败")
        def fetch_api():
            return requests.get(url)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except source_exc as e:
                msg = message or str(e)
                raise target_exc(msg) from e
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except source_exc as e:
                msg = message or str(e)
                raise target_exc(msg) from e
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# =============================================================================
# 异常分类工具
# =============================================================================

def is_retryable(exc: Exception) -> bool:
    """判断异常是否可重试
    
    Args:
        exc: 异常实例
        
    Returns:
        是否可重试
    """
    # 明确标记为可重试的异常
    if isinstance(exc, RetryableError):
        return True
    
    # 明确标记为不可重试的异常
    if isinstance(exc, NonRetryableError):
        return False
    
    # 常见可重试的网络错误
    retryable_exceptions = (
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
    )
    
    return isinstance(exc, retryable_exceptions)


def get_retry_after(exc: Exception, default: int = 60) -> int:
    """获取建议的重试等待时间
    
    Args:
        exc: 异常实例
        default: 默认等待时间（秒）
        
    Returns:
        建议的等待时间（秒）
    """
    if isinstance(exc, QBittorrentMonitorError) and exc.retry_after is not None:
        return exc.retry_after
    return default


def get_error_severity(exc: Exception) -> ErrorSeverity:
    """获取异常的严重程度
    
    Args:
        exc: 异常实例
        
    Returns:
        严重程度
    """
    if isinstance(exc, QBittorrentMonitorError):
        return exc.severity
    
    # 默认严重程度
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        return ErrorSeverity.CRITICAL
    
    return ErrorSeverity.ERROR


# =============================================================================
# 模块导出
# =============================================================================

__all__ = [
    # 全局异常处理器
    "GlobalExceptionHandler",
    
    # 装饰器
    "handle_exceptions",
    "retry_on_exception",
    "convert_exception",
    
    # 上下文管理器
    "exception_context",
    
    # 工具函数
    "wrap_exception",
    "is_retryable",
    "get_retry_after",
    "get_error_severity",
]
