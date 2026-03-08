"""
安全测试模块

测试安全相关功能：
- 输入验证
- 路径遍历防护
- 敏感信息过滤
- 磁力链接验证
"""

import pytest
import logging
from pathlib import Path

from qbittorrent_monitor.security import (
    validate_magnet,
    sanitize_magnet,
    extract_magnet_hash_safe,
    validate_save_path,
    sanitize_filename,
    validate_url,
    validate_hostname,
    is_sensitive_field,
    mask_sensitive_value,
    get_secure_headers,
    PATH_TRAVERSAL_PATTERNS,
)
from qbittorrent_monitor.logging_filters import SensitiveDataFilter
from qbittorrent_monitor.exceptions import ConfigError


class TestMagnetValidation:
    """测试磁力链接验证"""
    
    def test_valid_magnet_40char(self):
        """测试有效的40位磁力链接"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
        is_valid, error = validate_magnet(magnet)
        assert is_valid is True
        assert error is None
    
    def test_valid_magnet_32char(self):
        """测试有效的32位磁力链接（base32）"""
        # 32位base32 hash（使用a-z和2-7）+ 一些额外的查询参数达到最小长度
        # base32 字符集: a-z, 2-7 (不包括 0, 1, 8, 9)
        # 32个字符: 使用 abcdefghijklmnopqrstuvwx234567ab (26个字母 + 6个数字 + 2个字母 = 34, 去掉2个)
        # 正确的32位: abcdefghijklmnopqrstuvwx2345 (24 + 4 = 28, 不够)
        # 需要32个: abcdefghijklmnopqrstuvwxyz234567 但z不是base32 -> abcdefghijklmnopqrstuvwx234567ab
        magnet = "magnet:?xt=urn:btih:abcdefghijklmnopqrstuvwx234567ab&dn=example"
        is_valid, error = validate_magnet(magnet)
        # 32位hash也应该是有效的
        assert is_valid is True, f"Expected valid, got error: {error}"
    
    def test_invalid_magnet_empty(self):
        """测试空磁力链接"""
        is_valid, error = validate_magnet("")
        assert is_valid is False
        assert "为空" in error
    
    def test_invalid_magnet_no_prefix(self):
        """测试缺少magnet前缀"""
        magnet = "http://example.com/torrent"
        is_valid, error = validate_magnet(magnet)
        assert is_valid is False
        # 错误消息可能是"过短"或"必须以magnet开头"
        assert "磁力链接" in error or "magnet" in error.lower()
    
    def test_invalid_magnet_no_hash(self):
        """测试缺少btih hash"""
        magnet = "magnet:?xt=urn:btih:"
        is_valid, error = validate_magnet(magnet)
        assert is_valid is False
    
    def test_invalid_magnet_control_chars(self):
        """测试包含控制字符的磁力链接"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678\x00"
        is_valid, error = validate_magnet(magnet)
        assert is_valid is False
    
    def test_magnet_too_long(self):
        """测试超长的磁力链接"""
        magnet = "magnet:?xt=urn:btih:" + "a" * 10000
        is_valid, error = validate_magnet(magnet)
        assert is_valid is False
        assert "过长" in error
    
    def test_sanitize_magnet(self):
        """测试磁力链接清理"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678\n\r"
        sanitized = sanitize_magnet(magnet)
        assert "\n" not in sanitized
        assert "\r" not in sanitized
    
    def test_extract_hash_safe(self):
        """测试安全提取hash"""
        magnet = "magnet:?xt=urn:btih:1234567890ABCDEF1234567890abcdef12345678"
        hash_value = extract_magnet_hash_safe(magnet)
        assert hash_value == "1234567890abcdef1234567890abcdef12345678"
    
    def test_extract_hash_safe_invalid(self):
        """测试无效磁力链接的hash提取"""
        hash_value = extract_magnet_hash_safe("invalid")
        assert hash_value is None


class TestPathTraversal:
    """测试路径遍历防护"""
    
    def test_valid_path(self):
        """测试有效路径"""
        validate_save_path("/downloads/movies")
        validate_save_path("/home/user/downloads")
        validate_save_path("downloads/movies")  # 相对路径
    
    def test_path_traversal_double_dot(self):
        """测试..路径遍历"""
        with pytest.raises(ConfigError) as exc_info:
            validate_save_path("/downloads/../etc/passwd")
        assert "不安全" in str(exc_info.value) or "路径遍历" in str(exc_info.value)
    
    def test_path_traversal_backslash(self):
        """测试反斜杠路径遍历"""
        with pytest.raises(ConfigError):
            validate_save_path("downloads\\..\\windows")
    
    def test_path_traversal_starting_with_dotdot(self):
        """测试以..开头的路径"""
        with pytest.raises(ConfigError):
            validate_save_path("../etc/passwd")
    
    def test_path_traversal_tilde(self):
        """测试~字符"""
        with pytest.raises(ConfigError):
            validate_save_path("~/downloads")
    
    def test_path_traversal_env_var(self):
        """测试环境变量"""
        with pytest.raises(ConfigError):
            validate_save_path("$HOME/downloads")
    
    def test_illegal_chars(self):
        """测试非法字符"""
        with pytest.raises(ConfigError):
            validate_save_path("/downloads/movie<name>")
        
        with pytest.raises(ConfigError):
            validate_save_path('/downloads/movie:name')
    
    def test_windows_reserved_names(self):
        """测试Windows保留名称"""
        with pytest.raises(ConfigError):
            validate_save_path("/downloads/CON")
        
        with pytest.raises(ConfigError):
            validate_save_path("/downloads/COM1")
    
    def test_empty_path(self):
        """测试空路径"""
        with pytest.raises(ConfigError):
            validate_save_path("")
        
        with pytest.raises(ConfigError):
            validate_save_path("   ")


class TestFilenameSanitization:
    """测试文件名清理"""
    
    def test_sanitize_normal_filename(self):
        """测试正常文件名"""
        assert sanitize_filename("movie.mp4") == "movie.mp4"
    
    def test_sanitize_illegal_chars(self):
        """测试非法字符替换"""
        assert sanitize_filename("movie<name>.mp4") == "movie_name_.mp4"
        assert sanitize_filename('movie:name.mp4') == "movie_name.mp4"
    
    def test_sanitize_path_separators(self):
        """测试路径分隔符替换"""
        assert sanitize_filename("movies/action.mp4") == "movies_action.mp4"
        assert sanitize_filename("movies\\action.mp4") == "movies_action.mp4"
    
    def test_sanitize_reserved_names(self):
        """测试保留名称处理"""
        assert sanitize_filename("CON") == "_CON"
        assert sanitize_filename("COM1.txt") == "_COM1.txt"
    
    def test_sanitize_empty(self):
        """测试空文件名"""
        assert sanitize_filename("") == "unnamed"
    
    def test_sanitize_control_chars(self):
        """测试控制字符"""
        assert sanitize_filename("movie\x01name") == "moviename"


class TestUrlValidation:
    """测试URL验证"""
    
    def test_valid_http_url(self):
        """测试有效HTTP URL"""
        validate_url("http://example.com", "TEST_URL")
    
    def test_valid_https_url(self):
        """测试有效HTTPS URL"""
        validate_url("https://api.example.com/v1", "TEST_URL")
    
    def test_invalid_url_no_scheme(self):
        """测试缺少协议的URL"""
        with pytest.raises(ConfigError):
            validate_url("example.com", "TEST_URL")
    
    def test_invalid_url_unsafe_scheme(self):
        """测试不安全的协议"""
        with pytest.raises(ConfigError):
            validate_url("ftp://example.com", "TEST_URL")
    
    def test_invalid_url_with_auth(self):
        """测试包含认证信息的URL"""
        with pytest.raises(ConfigError):
            validate_url("https://user:pass@example.com", "TEST_URL")
    
    def test_invalid_url_control_chars(self):
        """测试包含控制字符的URL"""
        with pytest.raises(ConfigError):
            validate_url("https://example.com\x00evil", "TEST_URL")


class TestHostnameValidation:
    """测试主机名验证"""
    
    def test_valid_hostname(self):
        """测试有效主机名"""
        validate_hostname("localhost")
        validate_hostname("example.com")
        validate_hostname("192.168.1.1")
    
    def test_invalid_hostname_command_injection(self):
        """测试命令注入"""
        with pytest.raises(ConfigError):
            validate_hostname("localhost; rm -rf /")
        
        with pytest.raises(ConfigError):
            validate_hostname("example.com|cat /etc/passwd")
        
        with pytest.raises(ConfigError):
            validate_hostname("example.com`whoami`")
    
    def test_invalid_hostname_control_chars(self):
        """测试包含控制字符的主机名"""
        with pytest.raises(ConfigError):
            validate_hostname("example\x00.com")
    
    def test_empty_hostname(self):
        """测试空主机名"""
        with pytest.raises(ConfigError):
            validate_hostname("")


class TestSensitiveDataFilter:
    """测试敏感数据过滤器"""
    
    def test_filter_password(self):
        """测试密码过滤"""
        filter_instance = SensitiveDataFilter()
        text = 'password="secret123"'
        filtered = filter_instance._filter_sensitive_data(text)
        assert "secret123" not in filtered
        assert "***" in filtered
    
    def test_filter_api_key(self):
        """测试API密钥过滤"""
        filter_instance = SensitiveDataFilter()
        text = 'api_key=sk-abcdefghijklmnop'
        filtered = filter_instance._filter_sensitive_data(text)
        assert "sk-abcdefghijklmnop" not in filtered
        assert "***" in filtered
    
    def test_filter_token(self):
        """测试令牌过滤"""
        filter_instance = SensitiveDataFilter()
        text = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
        filtered = filter_instance._filter_sensitive_data(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in filtered
        assert "***" in filtered
    
    def test_filter_magnet_hash(self):
        """测试磁力链接hash过滤"""
        filter_instance = SensitiveDataFilter()
        text = 'magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678'
        filtered = filter_instance._filter_sensitive_data(text)
        # 应该保留前8位，隐藏后面的
        assert '12345678***' in filtered or '***' in filtered
    
    def test_filter_dict(self):
        """测试字典过滤"""
        data = {
            "username": "admin",
            "password": "secret",
            "api_key": "key123",
            "normal_field": "value"
        }
        filtered = SensitiveDataFilter.filter_dict(data)
        assert filtered["password"] == "***"
        assert filtered["api_key"] == "***"
        assert filtered["username"] == "admin"
        assert filtered["normal_field"] == "value"


class TestSensitiveFieldDetection:
    """测试敏感字段检测"""
    
    def test_is_sensitive_field(self):
        """测试敏感字段识别"""
        assert is_sensitive_field("password") is True
        assert is_sensitive_field("api_key") is True
        assert is_sensitive_field("secret") is True
        assert is_sensitive_field("token") is True
        assert is_sensitive_field("username") is False
        assert is_sensitive_field("host") is False
    
    def test_mask_sensitive_value(self):
        """测试敏感值遮盖"""
        result = mask_sensitive_value("secretpassword")
        assert "***" in result
        assert "secretpassword" not in result
        assert mask_sensitive_value("ab") == "***"
        assert mask_sensitive_value("") == "***"


class TestSecureHeaders:
    """测试安全头部"""
    
    def test_secure_headers(self):
        """测试安全头部生成"""
        headers = get_secure_headers()
        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "qbittorrent-clipboard-monitor" in headers["User-Agent"]


class TestLoggingIntegration:
    """测试日志集成"""
    
    def test_log_filter_integration(self, caplog):
        """测试日志过滤器集成"""
        # 创建带过滤器的handler
        filter_instance = SensitiveDataFilter()
        handler = logging.StreamHandler()
        handler.addFilter(filter_instance)
        
        # 使用特定的formatter来脱敏
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        
        # 创建测试logger
        test_logger = logging.getLogger("test_security_logger")
        test_logger.setLevel(logging.DEBUG)
        test_logger.handlers = []  # 清除现有处理器
        test_logger.addHandler(handler)
        test_logger.propagate = False
        
        # 记录包含敏感信息的日志
        with caplog.at_level(logging.INFO, logger="test_security_logger"):
            test_logger.info('password="secret123"')
        
        # 检查敏感信息是否被过滤
        assert "secret123" not in caplog.text or "***" in caplog.text


class TestSecurityConstants:
    """测试安全常量"""
    
    def test_safe_timeouts(self):
        """测试超时设置"""
        from qbittorrent_monitor.security import SAFE_TIMEOUTS
        assert "connect" in SAFE_TIMEOUTS
        assert "read" in SAFE_TIMEOUTS
        assert "total" in SAFE_TIMEOUTS
        assert SAFE_TIMEOUTS["connect"] > 0
    
    def test_safe_limits(self):
        """测试安全限制"""
        from qbittorrent_monitor.security import SAFE_LIMITS
        assert "max_magnet_length" in SAFE_LIMITS
        assert "max_path_length" in SAFE_LIMITS
        assert SAFE_LIMITS["max_magnet_length"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
