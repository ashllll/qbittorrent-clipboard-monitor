"""异常体系测试

测试统一的错误代码体系和异常类。
"""

import logging
import pytest

from qbittorrent_monitor.common.exceptions import (
    QBMonitorError,
    ConfigError,
    QBClientError,
    QBAuthError,
    QBConnectionError,
    AIError,
    ClassificationError,
    ValidationError,
    SecurityError,
    ErrorCode,
    get_error_code,
    format_error_message,
)


class TestErrorCode:
    """测试错误代码枚举"""
    
    def test_error_code_format(self):
        """测试错误代码格式"""
        for code in ErrorCode:
            # 错误代码应为6位数字
            assert len(code.value) == 6
            assert code.value.isdigit()
    
    def test_error_code_categories(self):
        """测试错误代码分类"""
        # 通用错误
        assert ErrorCode.UNKNOWN_ERROR.value.startswith("01")
        # 配置错误
        assert ErrorCode.CONFIG_INVALID.value.startswith("10")
        # qBittorrent 错误
        assert ErrorCode.QB_AUTH_FAILED.value.startswith("20")
        # AI 错误
        assert ErrorCode.AI_REQUEST_FAILED.value.startswith("30")


class TestQBMonitorError:
    """测试基础异常类"""
    
    def test_basic_error(self):
        """测试基础错误创建"""
        error = QBMonitorError("测试错误")
        assert error.message == "测试错误"
        assert error.error_code == ErrorCode.UNKNOWN_ERROR
        assert str(error) == "[015000] 测试错误"
    
    def test_error_with_code(self):
        """测试带错误代码的异常"""
        error = QBMonitorError(
            "配置错误",
            error_code=ErrorCode.CONFIG_INVALID,
        )
        assert error.error_code == ErrorCode.CONFIG_INVALID
        assert "[101000]" in str(error)
    
    def test_error_with_context(self):
        """测试带上下文的异常"""
        error = QBMonitorError(
            "配置错误",
            error_code=ErrorCode.CONFIG_FILE_NOT_FOUND,
            context={"path": "/tmp/config.json", "reason": "文件不存在"},
        )
        error_str = str(error)
        assert "path=/tmp/config.json" in error_str
        assert "reason=文件不存在" in error_str
    
    def test_error_with_cause(self):
        """测试带原始异常的异常"""
        cause = ValueError("原始错误")
        error = QBMonitorError(
            "处理失败",
            cause=cause,
        )
        assert error.cause == cause
        assert "ValueError: 原始错误" in str(error)
    
    def test_error_to_dict(self):
        """测试转换为字典"""
        error = QBMonitorError(
            "测试错误",
            error_code=ErrorCode.UNKNOWN_ERROR,
            context={"key": "value"},
        )
        data = error.to_dict()
        assert data["error_code"] == "015000"
        assert data["message"] == "测试错误"
        assert data["context"] == {"key": "value"}
    
    def test_error_log(self, caplog):
        """测试日志记录"""
        logger = logging.getLogger("test")
        error = QBMonitorError("测试错误")
        
        with caplog.at_level(logging.ERROR):
            error.log(logger)
        
        assert "测试错误" in caplog.text


class TestConfigError:
    """测试配置错误"""
    
    def test_default_error_code(self):
        """测试默认错误代码"""
        error = ConfigError("配置错误")
        assert error.error_code == ErrorCode.CONFIG_INVALID
    
    def test_custom_error_code(self):
        """测试自定义错误代码"""
        error = ConfigError(
            "文件不存在",
            error_code=ErrorCode.CONFIG_FILE_NOT_FOUND,
        )
        assert error.error_code == ErrorCode.CONFIG_FILE_NOT_FOUND


class TestQBClientErrors:
    """测试 qBittorrent 客户端错误"""
    
    def test_auth_error(self):
        """测试认证错误"""
        error = QBAuthError()
        assert error.error_code == ErrorCode.QB_AUTH_FAILED
        assert "认证失败" in str(error)
    
    def test_auth_error_with_message(self):
        """测试带消息的认证错误"""
        error = QBAuthError("用户名或密码错误")
        assert "用户名或密码错误" in str(error)
    
    def test_connection_error(self):
        """测试连接错误"""
        error = QBConnectionError()
        assert error.error_code == ErrorCode.QB_CONNECTION_FAILED
        assert "无法连接到" in str(error)
    
    def test_connection_error_with_context(self):
        """测试带上下文的连接错误"""
        error = QBConnectionError(
            context={"host": "192.168.1.1", "port": 8080},
        )
        error_str = str(error)
        assert "host=192.168.1.1" in error_str
        assert "port=8080" in error_str


class TestAIError:
    """测试 AI 错误"""
    
    def test_default_error_code(self):
        """测试默认错误代码"""
        error = AIError("AI 请求失败")
        assert error.error_code == ErrorCode.AI_REQUEST_FAILED
    
    def test_timeout_error(self):
        """测试超时错误"""
        error = AIError(
            "请求超时",
            error_code=ErrorCode.AI_TIMEOUT,
        )
        assert error.error_code == ErrorCode.AI_TIMEOUT


class TestValidationError:
    """测试验证错误"""
    
    def test_basic_validation(self):
        """测试基础验证错误"""
        error = ValidationError("验证失败")
        assert error.error_code == ErrorCode.INVALID_ARGUMENT
    
    def test_validation_with_field(self):
        """测试带字段名的验证错误"""
        error = ValidationError(
            "值无效",
            field="port",
            value=99999,
        )
        error_str = str(error)
        assert "port" in error_str
        assert "99999" in error_str


class TestHelperFunctions:
    """测试辅助函数"""
    
    def test_get_error_code_with_qbmonitor_error(self):
        """测试从 QBMonitorError 获取错误代码"""
        error = ConfigError("测试")
        code = get_error_code(error)
        assert code == ErrorCode.CONFIG_INVALID
    
    def test_get_error_code_with_standard_error(self):
        """测试从标准异常获取错误代码"""
        error = ValueError("测试")
        code = get_error_code(error)
        assert code == ErrorCode.UNKNOWN_ERROR
    
    def test_format_error_message_basic(self):
        """测试基础错误消息格式化"""
        error = QBMonitorError(
            "测试错误",
            error_code=ErrorCode.UNKNOWN_ERROR,
        )
        message = format_error_message(error)
        assert "[015000]" in message
        assert "测试错误" in message
    
    def test_format_error_message_with_context(self):
        """测试带上下文的错误消息格式化"""
        error = QBMonitorError(
            "测试错误",
            context={"key": "value"},
        )
        message = format_error_message(error, include_context=True)
        assert "key=value" in message
    
    def test_format_error_message_without_context(self):
        """测试不包含上下文的错误消息格式化"""
        error = QBMonitorError(
            "测试错误",
            context={"key": "value"},
        )
        message = format_error_message(error, include_context=False)
        assert "key=value" not in message
    
    def test_format_error_message_standard_exception(self):
        """测试标准异常的消息格式化"""
        error = ValueError("标准错误")
        message = format_error_message(error)
        assert "[ValueError]" in message
        assert "标准错误" in message
