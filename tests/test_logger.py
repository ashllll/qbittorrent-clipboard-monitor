"""
结构化日志模块测试
"""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from qbittorrent_monitor.logger import (
    LogConfig,
    LogFormat,
    JsonFormatter,
    ColoredFormatter,
    DetailedFormatter,
    StructuredLogger,
    create_formatter,
    setup_logging,
    get_logger,
    configure_from_dict,
)
from qbittorrent_monitor.logging_filters import SensitiveDataFilter


class TestLogConfig(TestCase):
    """测试日志配置类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = LogConfig()
        self.assertEqual(config.level, "INFO")
        self.assertEqual(config.format, "text")
        self.assertTrue(config.console_enabled)
        self.assertTrue(config.console_color)
        self.assertTrue(config.file_enabled)
        self.assertEqual(config.file_max_bytes, 10 * 1024 * 1024)
        self.assertEqual(config.file_backup_count, 5)
        self.assertEqual(config.file_max_age_days, 7)
    
    def test_config_to_dict(self):
        """测试配置转字典"""
        config = LogConfig(level="DEBUG", format="json")
        data = config.to_dict()
        self.assertEqual(data["level"], "DEBUG")
        self.assertEqual(data["format"], "json")
    
    def test_config_from_dict(self):
        """测试从字典创建配置"""
        data = {
            "level": "ERROR",
            "format": "detailed",
            "console_color": False,
            "file_max_bytes": 5 * 1024 * 1024,
        }
        config = LogConfig.from_dict(data)
        self.assertEqual(config.level, "ERROR")
        self.assertEqual(config.format, "detailed")
        self.assertFalse(config.console_color)
        self.assertEqual(config.file_max_bytes, 5 * 1024 * 1024)
    
    def test_config_from_dict_ignores_invalid_fields(self):
        """测试从字典创建配置时忽略无效字段"""
        data = {
            "level": "DEBUG",
            "invalid_field": "should_be_ignored",
            "another_invalid": 123,
        }
        config = LogConfig.from_dict(data)
        self.assertEqual(config.level, "DEBUG")
        # 确保其他字段仍为默认值
        self.assertEqual(config.format, "text")


class TestJsonFormatter(TestCase):
    """测试 JSON 格式化器"""
    
    def setUp(self):
        self.formatter = JsonFormatter()
        self.record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        self.record.funcName = "test_function"
    
    def test_basic_json_format(self):
        """测试基本 JSON 格式"""
        output = self.formatter.format(self.record)
        data = json.loads(output)
        
        self.assertEqual(data["level"], "INFO")
        self.assertEqual(data["logger"], "test")
        self.assertEqual(data["message"], "Test message")
        self.assertEqual(data["source"]["file"], "/test/file.py")
        self.assertEqual(data["source"]["line"], 42)
        self.assertEqual(data["source"]["function"], "test_function")
        self.assertIn("timestamp", data)
        self.assertIn("host", data)
        self.assertEqual(data["project"], "qb-monitor")
    
    def test_json_with_extra_fields(self):
        """测试带额外字段的 JSON 格式"""
        self.record.magnet_hash = "abc123"
        self.record.category = "movies"
        
        output = self.formatter.format(self.record)
        data = json.loads(output)
        
        self.assertEqual(data["extra"]["magnet_hash"], "abc123")
        self.assertEqual(data["extra"]["category"], "movies")


class TestColoredFormatter(TestCase):
    """测试彩色格式化器"""
    
    def test_color_codes_added(self):
        """测试颜色代码添加"""
        formatter = ColoredFormatter(use_color=True)
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="/test/file.py",
            lineno=1,
            msg="Error message",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        # 检查是否包含颜色代码
        self.assertIn("\033[", output)  # ANSI 转义序列
    
    def test_no_color_when_disabled(self):
        """测试禁用颜色时不添加颜色代码"""
        formatter = ColoredFormatter(use_color=False)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test/file.py",
            lineno=1,
            msg="Info message",
            args=(),
            exc_info=None,
        )
        
        output = formatter.format(record)
        self.assertNotIn("\033[", output)


class TestDetailedFormatter(TestCase):
    """测试详细格式化器"""
    
    def test_detailed_format(self):
        """测试详细格式包含更多信息"""
        formatter = DetailedFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="/test/file.py",
            lineno=42,
            msg="Debug message",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_func"
        
        output = formatter.format(record)
        self.assertIn("/test/file.py", output)
        self.assertIn("42", output)
        self.assertIn("test_func", output)
        self.assertIn("Debug message", output)


class TestCreateFormatter(TestCase):
    """测试格式化器创建函数"""
    
    def test_create_text_formatter(self):
        """测试创建文本格式化器"""
        formatter = create_formatter(LogFormat.TEXT, use_color=False)
        self.assertIsInstance(formatter, logging.Formatter)
    
    def test_create_json_formatter(self):
        """测试创建 JSON 格式化器"""
        formatter = create_formatter(LogFormat.JSON)
        self.assertIsInstance(formatter, JsonFormatter)
    
    def test_create_detailed_formatter(self):
        """测试创建详细格式化器"""
        formatter = create_formatter(LogFormat.DETAILED)
        self.assertIsInstance(formatter, DetailedFormatter)


class TestStructuredLogger(TestCase):
    """测试结构化日志记录器"""
    
    def setUp(self):
        # 创建一个内存处理器来捕获日志
        self.logger = get_logger("test_structured")
        self.handler = logging.Handler()
        self.handler.records = []
        self.handler.emit = lambda record: self.handler.records.append(record)
        
        # 清除并添加处理器
        self.logger._logger.handlers = []
        self.logger._logger.addHandler(self.handler)
        self.logger._logger.setLevel(logging.DEBUG)
    
    def test_basic_logging(self):
        """测试基本日志记录"""
        self.logger.info("Test message")
        self.assertEqual(len(self.handler.records), 1)
        self.assertEqual(self.handler.records[0].msg, "Test message")
    
    def test_bind_context(self):
        """测试上下文绑定"""
        context_logger = self.logger.bind(request_id="12345")
        context_logger.info("Message with context")
        
        record = self.handler.records[0]
        self.assertEqual(record.request_id, "12345")
    
    def test_nested_context(self):
        """测试嵌套上下文"""
        logger1 = self.logger.bind(a=1)
        logger2 = logger1.bind(b=2)
        logger2.info("Nested context")
        
        record = self.handler.records[0]
        self.assertEqual(record.a, 1)
        self.assertEqual(record.b, 2)


class TestSetupLogging(TestCase):
    """测试日志设置函数"""
    
    def test_setup_logging_with_default_config(self):
        """测试使用默认配置设置日志"""
        # 清除根日志记录器
        root_logger = logging.getLogger()
        root_logger.handlers = []
        
        logger = setup_logging()
        self.assertIsNotNone(logger)
        # 应该至少有一个处理器（控制台）
        self.assertGreaterEqual(len(logger.handlers), 1)
    
    def test_setup_logging_with_custom_config(self):
        """测试使用自定义配置设置日志"""
        root_logger = logging.getLogger()
        root_logger.handlers = []
        
        config = LogConfig(
            level="DEBUG",
            format="json",
            console_enabled=True,
            file_enabled=False,
        )
        
        logger = setup_logging(config)
        self.assertEqual(logger.level, logging.DEBUG)


class TestConfigureFromDict(TestCase):
    """测试从字典配置日志"""
    
    def test_configure_from_dict(self):
        """测试从字典配置"""
        root_logger = logging.getLogger()
        root_logger.handlers = []
        
        config_dict = {
            "logging": {
                "level": "WARNING",
                "format": "json",
                "console_color": False,
            }
        }
        
        logger = configure_from_dict(config_dict)
        self.assertEqual(logger.level, logging.WARNING)


class TestSensitiveDataFilterIntegration(TestCase):
    """测试敏感信息过滤器集成"""
    
    def test_filter_applied_to_handlers(self):
        """测试过滤器应用到处理器"""
        root_logger = logging.getLogger("test_sensitive")
        root_logger.handlers = []
        root_logger.setLevel(logging.DEBUG)
        
        config = LogConfig(
            level="INFO",
            format="text",
            console_enabled=True,
            file_enabled=False,
        )
        
        setup_logging(config)
        
        # 检查是否有过滤器
        for handler in logging.getLogger().handlers:
            filters = [f for f in handler.filters if isinstance(f, SensitiveDataFilter)]
            # 至少有一个 SensitiveDataFilter
            self.assertGreaterEqual(len(filters), 1)


class TestLogFormatEnum(TestCase):
    """测试日志格式枚举"""
    
    def test_enum_values(self):
        """测试枚举值"""
        self.assertEqual(LogFormat.TEXT.value, "text")
        self.assertEqual(LogFormat.JSON.value, "json")
        self.assertEqual(LogFormat.DETAILED.value, "detailed")
    
    def test_enum_from_string(self):
        """测试从字符串创建枚举"""
        fmt = LogFormat("json")
        self.assertEqual(fmt, LogFormat.JSON)


if __name__ == "__main__":
    import unittest
    unittest.main()
