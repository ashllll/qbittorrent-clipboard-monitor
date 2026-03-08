"""装饰器测试

测试统一的错误处理、重试机制和日志记录装饰器。
"""

import asyncio
import logging
import time
from unittest.mock import Mock, patch

import pytest

from qbittorrent_monitor.common.decorators import (
    safe_operation,
    async_safe_operation,
    retry_with_backoff,
    log_execution_time,
    validate_input,
    singleton,
    deprecated,
)
from qbittorrent_monitor.common.exceptions import (
    QBMonitorError,
    ValidationError,
    ErrorCode,
)


class TestSafeOperation:
    """测试安全操作装饰器（同步版本）"""
    
    def test_successful_execution(self):
        """测试成功执行"""
        @safe_operation("操作失败")
        def success_func():
            return "success"
        
        assert success_func() == "success"
    
    def test_exception_handling(self):
        """测试异常处理"""
        @safe_operation("操作失败", error_code=ErrorCode.UNKNOWN_ERROR)
        def fail_func():
            raise ValueError("原始错误")
        
        with pytest.raises(QBMonitorError) as exc_info:
            fail_func()
        
        assert "操作失败" in str(exc_info.value)
        assert "原始错误" in str(exc_info.value)
        assert exc_info.value.error_code == ErrorCode.UNKNOWN_ERROR
    
    def test_no_reraise_with_default_return(self):
        """测试不重抛异常并返回默认值"""
        @safe_operation(
            "操作失败",
            reraise=False,
            default_return="default",
        )
        def fail_func():
            raise ValueError("原始错误")
        
        result = fail_func()
        assert result == "default"
    
    def test_exclude_exceptions(self):
        """测试排除特定异常"""
        @safe_operation(
            "操作失败",
            exclude_exceptions=(ValueError,),
        )
        def fail_func():
            raise ValueError("原始错误")
        
        with pytest.raises(ValueError):
            fail_func()
    
    def test_logging_on_error(self, caplog):
        """测试错误时记录日志"""
        @safe_operation("操作失败", log_level=logging.ERROR)
        def fail_func():
            raise ValueError("原始错误")
        
        with caplog.at_level(logging.ERROR):
            try:
                fail_func()
            except QBMonitorError:
                pass
        
        assert "操作失败" in caplog.text


class TestAsyncSafeOperation:
    """测试安全操作装饰器（异步版本）"""
    
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """测试成功执行"""
        @async_safe_operation("操作失败")
        async def success_func():
            return "success"
        
        result = await success_func()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """测试异常处理"""
        @async_safe_operation("操作失败", error_code=ErrorCode.UNKNOWN_ERROR)
        async def fail_func():
            raise ValueError("原始错误")
        
        with pytest.raises(QBMonitorError) as exc_info:
            await fail_func()
        
        assert "操作失败" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_cancelled_error_not_caught(self):
        """测试取消错误不被捕获"""
        @async_safe_operation("操作失败")
        async def cancel_func():
            raise asyncio.CancelledError()
        
        with pytest.raises(asyncio.CancelledError):
            await cancel_func()
    
    @pytest.mark.asyncio
    async def test_no_reraise_with_default_return(self):
        """测试不重抛异常并返回默认值"""
        @async_safe_operation(
            "操作失败",
            reraise=False,
            default_return="default",
        )
        async def fail_func():
            raise ValueError("原始错误")
        
        result = await fail_func()
        assert result == "default"


class TestRetryWithBackoff:
    """测试指数退避重试装饰器"""
    
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """测试成功执行不重试"""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await success_func()
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """测试失败时重试"""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        async def fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("失败")
        
        with pytest.raises(ValueError):
            await fail_func()
        
        assert call_count == 3  # 初始 + 2次重试
    
    @pytest.mark.asyncio
    async def test_retry_with_success_after_failure(self):
        """测试失败后成功"""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def sometimes_fail():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("失败")
            return "success"
        
        result = await sometimes_fail()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_specific_exceptions(self):
        """测试只重试特定异常"""
        call_count = 0
        
        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            retry_on=(ValueError,),
        )
        async def raise_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("类型错误")
        
        with pytest.raises(TypeError):
            await raise_type_error()
        
        assert call_count == 1  # 不重试
    
    @pytest.mark.asyncio
    async def test_cancelled_error_not_retried(self):
        """测试取消错误不重试"""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        async def cancel_func():
            nonlocal call_count
            call_count += 1
            raise asyncio.CancelledError()
        
        with pytest.raises(asyncio.CancelledError):
            await cancel_func()
        
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        """测试重试回调"""
        retry_calls = []
        
        def on_retry(exception, attempt, delay):
            retry_calls.append((type(exception).__name__, attempt, delay))
        
        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            on_retry=on_retry,
        )
        async def fail_func():
            raise ValueError("失败")
        
        with pytest.raises(ValueError):
            await fail_func()
        
        assert len(retry_calls) == 2
        assert retry_calls[0][0] == "ValueError"
        assert retry_calls[0][1] == 1


class TestLogExecutionTime:
    """测试执行时间日志装饰器"""
    
    def test_sync_function_timing(self, caplog):
        """测试同步函数计时"""
        @log_execution_time(logging.DEBUG, "{func_name} 耗时: {elapsed:.3f}s")
        def slow_func():
            time.sleep(0.01)
            return "done"
        
        with caplog.at_level(logging.DEBUG):
            result = slow_func()
        
        assert result == "done"
        assert "slow_func" in caplog.text
        assert "耗时:" in caplog.text
    
    @pytest.mark.asyncio
    async def test_async_function_timing(self, caplog):
        """测试异步函数计时"""
        @log_execution_time(logging.DEBUG, "{func_name} 耗时: {elapsed:.3f}s")
        async def slow_async_func():
            await asyncio.sleep(0.01)
            return "done"
        
        with caplog.at_level(logging.DEBUG):
            result = await slow_async_func()
        
        assert result == "done"
        assert "slow_async_func" in caplog.text
    
    def test_min_time_filter(self, caplog):
        """测试最小时间过滤"""
        @log_execution_time(logging.DEBUG, min_time=1.0)
        def fast_func():
            return "done"
        
        with caplog.at_level(logging.DEBUG):
            result = fast_func()
        
        assert result == "done"
        assert caplog.text == ""


class TestValidateInput:
    """测试输入验证装饰器"""
    
    def test_successful_validation(self):
        """测试验证通过"""
        def validate_positive(n):
            if n <= 0:
                raise ValueError("必须是正数")
        
        @validate_input(validate_positive)
        def process_number(n: int) -> int:
            return n * 2
        
        assert process_number(5) == 10
    
    def test_validation_failure(self):
        """测试验证失败"""
        def validate_positive(n):
            if n <= 0:
                raise ValueError("必须是正数")
        
        @validate_input(validate_positive)
        def process_number(n: int) -> int:
            return n * 2
        
        with pytest.raises(ValidationError) as exc_info:
            process_number(-5)
        
        assert "验证失败" in str(exc_info.value)
        assert "n" in str(exc_info.value)


class TestSingleton:
    """测试单例模式装饰器"""
    
    def test_single_instance(self):
        """测试只创建一个实例"""
        @singleton
        class TestClass:
            def __init__(self):
                self.value = 0
        
        obj1 = TestClass()
        obj2 = TestClass()
        
        assert obj1 is obj2
        
        obj1.value = 42
        assert obj2.value == 42


class TestDeprecated:
    """测试弃用警告装饰器"""
    
    def test_deprecation_warning(self):
        """测试弃用警告"""
        import warnings
        
        @deprecated("2.0.0", removed_in="3.0.0", alternative="new_func")
        def old_func():
            return "result"
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = old_func()
            
            assert result == "result"
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "2.0.0" in str(w[0].message)
            assert "3.0.0" in str(w[0].message)
            assert "new_func" in str(w[0].message)
