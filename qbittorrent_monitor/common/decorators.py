"""通用装饰器模块

提供统一的错误处理、重试机制、日志记录等装饰器。
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
import time
from typing import (
    Any,
    Callable,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from .exceptions import (
    QBMonitorError,
    ErrorCode,
    format_error_message,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# 默认重试配置
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 60.0
DEFAULT_EXPONENTIAL_BASE = 2.0
DEFAULT_JITTER = 0.2


def safe_operation(
    error_message: str = "操作失败",
    error_code: Optional[ErrorCode] = None,
    reraise: bool = True,
    log_level: int = logging.ERROR,
    default_return: Any = None,
    exclude_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
) -> Callable[[F], F]:
    """安全操作装饰器（同步版本）
    
    统一捕获和处理异常，提供标准化的错误日志和返回值。
    
    Args:
        error_message: 错误消息前缀
        error_code: 错误代码
        reraise: 是否重新抛出异常
        log_level: 日志级别
        default_return: 失败时的默认返回值
        exclude_exceptions: 不处理的异常类型（直接抛出）
    
    Returns:
        装饰后的函数
    
    Example:
        >>> @safe_operation("读取配置失败", ErrorCode.CONFIG_FILE_NOT_FOUND)
        ... def load_config():
        ...     with open("config.json") as f:
        ...         return json.load(f)
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 检查是否是需要排除的异常
                if exclude_exceptions and isinstance(e, exclude_exceptions):
                    raise
                
                # 构建错误消息
                full_message = f"{error_message}: {str(e)}"
                
                # 记录日志
                if isinstance(e, QBMonitorError):
                    e.log(logger, log_level)
                else:
                    logger.log(log_level, full_message, exc_info=True)
                
                if reraise:
                    if isinstance(e, QBMonitorError):
                        raise
                    raise QBMonitorError(
                        full_message,
                        error_code=error_code or ErrorCode.UNKNOWN_ERROR,
                        context={"function": func.__name__},
                        cause=e,
                    ) from e
                
                return default_return
        
        return cast(F, wrapper)
    return decorator


def async_safe_operation(
    error_message: str = "操作失败",
    error_code: Optional[ErrorCode] = None,
    reraise: bool = True,
    log_level: int = logging.ERROR,
    default_return: Any = None,
    exclude_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
) -> Callable[[F], F]:
    """安全操作装饰器（异步版本）
    
    统一捕获和处理异步异常，提供标准化的错误日志和返回值。
    
    Args:
        error_message: 错误消息前缀
        error_code: 错误代码
        reraise: 是否重新抛出异常
        log_level: 日志级别
        default_return: 失败时的默认返回值
        exclude_exceptions: 不处理的异常类型（直接抛出）
    
    Returns:
        装饰后的异步函数
    
    Example:
        >>> @async_safe_operation("API调用失败", ErrorCode.QB_API_ERROR)
        ... async def fetch_data():
        ...     async with aiohttp.ClientSession() as session:
        ...         return await session.get("https://api.example.com")
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError:
                # 取消操作不处理，直接抛出
                raise
            except Exception as e:
                # 检查是否是需要排除的异常
                if exclude_exceptions and isinstance(e, exclude_exceptions):
                    raise
                
                # 构建错误消息
                full_message = f"{error_message}: {str(e)}"
                
                # 记录日志
                if isinstance(e, QBMonitorError):
                    e.log(logger, log_level)
                else:
                    logger.log(log_level, full_message, exc_info=True)
                
                if reraise:
                    if isinstance(e, QBMonitorError):
                        raise
                    raise QBMonitorError(
                        full_message,
                        error_code=error_code or ErrorCode.UNKNOWN_ERROR,
                        context={"function": func.__name__},
                        cause=e,
                    ) from e
                
                return default_return
        
        return cast(F, wrapper)
    return decorator


def retry_with_backoff(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    exponential_base: float = DEFAULT_EXPONENTIAL_BASE,
    jitter: float = DEFAULT_JITTER,
    retry_on: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[Exception, int, float], None]] = None,
    on_give_up: Optional[Callable[[Exception], None]] = None,
) -> Callable[[F], F]:
    """指数退避重试装饰器
    
    支持抖动（jitter）的指数退避重试机制。
    
    Args:
        max_retries: 最大重试次数
        base_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数基数
        jitter: 抖动比例（0.0-1.0）
        retry_on: 需要重试的异常类型，None 表示所有异常
        on_retry: 重试回调函数，参数为 (异常, 重试次数, 延迟时间)
        on_give_up: 放弃重试时的回调函数
    
    Returns:
        装饰后的异步函数
    
    Example:
        >>> @retry_with_backoff(max_retries=3, base_delay=1.0)
        ... async def connect_to_server():
        ...     # 可能失败的网络操作
        ...     pass
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except asyncio.CancelledError:
                    # 取消操作不重试
                    raise
                except Exception as e:
                    last_exception = e
                    
                    # 检查是否需要重试
                    if retry_on and not isinstance(e, retry_on):
                        raise
                    
                    if attempt < max_retries:
                        # 计算指数退避延迟
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        
                        # 添加抖动
                        if jitter > 0:
                            jitter_amount = delay * jitter
                            delay += random.uniform(-jitter_amount, jitter_amount)
                            delay = max(0, delay)  # 确保非负
                        
                        # 执行重试回调
                        if on_retry:
                            try:
                                on_retry(e, attempt + 1, delay)
                            except Exception:
                                pass
                        
                        # 记录重试日志
                        logger.warning(
                            f"{func.__name__} 第 {attempt + 1}/{max_retries + 1} 次尝试失败，"
                            f"{delay:.2f}秒后重试: {str(e)}"
                        )
                        
                        await asyncio.sleep(delay)
                    else:
                        # 重试耗尽
                        logger.error(
                            f"{func.__name__} 在 {max_retries + 1} 次尝试后仍然失败: {str(e)}"
                        )
                        
                        if on_give_up:
                            try:
                                on_give_up(e)
                            except Exception:
                                pass
            
            # 重试耗尽后抛出最后的异常
            if last_exception:
                raise last_exception
        
        return cast(F, wrapper)
    return decorator


def log_execution_time(
    level: int = logging.DEBUG,
    message: str = "{func_name} 执行耗时: {elapsed:.3f}秒",
    min_time: float = 0.0,
) -> Callable[[F], F]:
    """记录函数执行时间装饰器
    
    Args:
        level: 日志级别
        message: 日志消息模板，支持 {func_name}, {elapsed} 占位符
        min_time: 最小记录时间（秒），低于此值不记录
    
    Returns:
        装饰后的函数
    
    Example:
        >>> @log_execution_time(logging.INFO, "API调用耗时: {elapsed:.3f}s")
        ... async def api_call():
        ...     pass
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = time.time() - start_time
                if elapsed >= min_time:
                    log_msg = message.format(
                        func_name=func.__name__,
                        elapsed=elapsed,
                    )
                    logger.log(level, log_msg)
        
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.time() - start_time
                if elapsed >= min_time:
                    log_msg = message.format(
                        func_name=func.__name__,
                        elapsed=elapsed,
                    )
                    logger.log(level, log_msg)
        
        # 根据函数类型返回适当的包装器
        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)
    return decorator


def validate_input(
    *validators: Callable[[Any], None],
    error_code: Optional[ErrorCode] = None,
) -> Callable[[F], F]:
    """输入验证装饰器
    
    在函数执行前验证输入参数。
    
    Args:
        *validators: 验证器函数列表，每个函数接收一个参数并抛出异常
        error_code: 验证失败时的错误代码
    
    Returns:
        装饰后的函数
    
    Example:
        >>> def validate_positive(n):
        ...     if n <= 0:
        ...         raise ValueError("必须是正数")
        ...
        >>> @validate_input(validate_positive)
        ... def process_number(n: int) -> int:
        ...     return n * 2
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 获取绑定的参数
            import inspect
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            
            # 应用验证器
            for validator in validators:
                for name, value in bound.arguments.items():
                    try:
                        validator(value)
                    except Exception as e:
                        from .exceptions import ValidationError
                        raise ValidationError(
                            f"参数验证失败: {name}",
                            field=name,
                            value=value,
                        ) from e
            
            return func(*args, **kwargs)
        
        return cast(F, wrapper)
    return decorator


def singleton(cls: Type[T]) -> Type[T]:
    """单例模式装饰器
    
    确保类只有一个实例。
    
    Args:
        cls: 要装饰的类
    
    Returns:
        单例类
    
    Example:
        >>> @singleton
        ... class ConfigManager:
        ...     pass
    """
    instances: dict = {}
    
    @functools.wraps(cls)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return cast(Type[T], wrapper)


def deprecated(
    since: str,
    removed_in: Optional[str] = None,
    alternative: Optional[str] = None,
) -> Callable[[F], F]:
    """弃用警告装饰器
    
    标记函数为已弃用，并在调用时发出警告。
    
    Args:
        since: 从哪个版本开始弃用
        removed_in: 计划在哪个版本移除
        alternative: 替代方案
    
    Returns:
        装饰后的函数
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import warnings
            msg = f"{func.__name__} 已从 {since} 版本开始弃用"
            if removed_in:
                msg += f"，计划在 {removed_in} 版本移除"
            if alternative:
                msg += f"，请使用 {alternative} 代替"
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)
        
        return cast(F, wrapper)
    return decorator
