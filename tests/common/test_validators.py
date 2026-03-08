"""验证器测试

测试统一的输入验证函数和 Validator 类。
"""

import pytest

from qbittorrent_monitor.common.validators import (
    Validator,
    validate_port,
    validate_timeout,
    validate_retries,
    validate_interval,
    validate_log_level,
    validate_non_empty_string,
    validate_boolean,
    validate_range,
    validate_url_scheme,
    create_range_validator,
    # 常量
    MIN_PORT,
    MAX_PORT,
    MIN_TIMEOUT,
    MAX_TIMEOUT,
    MIN_RETRIES,
    MAX_RETRIES,
    MIN_CHECK_INTERVAL,
    MAX_CHECK_INTERVAL,
)
from qbittorrent_monitor.common.exceptions import ValidationError


class TestValidator:
    """测试 Validator 类"""
    
    def test_check_method(self):
        """测试 check 方法"""
        v = Validator()
        result = v.check("field", 123)
        assert result is v
        assert v.field_name == "field"
        assert v.value == 123
    
    def test_is_not_none_success(self):
        """测试非空验证成功"""
        v = Validator().check("field", "value").is_not_none()
        assert v.validate() == "value"
    
    def test_is_not_none_failure(self):
        """测试非空验证失败"""
        v = Validator().check("field", None).is_not_none()
        with pytest.raises(ValidationError) as exc_info:
            v.validate()
        assert "不能为 None" in str(exc_info.value)
    
    def test_is_string_success(self):
        """测试字符串验证成功"""
        v = Validator().check("field", "test").is_string()
        assert v.validate() == "test"
    
    def test_is_string_failure(self):
        """测试字符串验证失败"""
        v = Validator().check("field", 123).is_string()
        with pytest.raises(ValidationError) as exc_info:
            v.validate()
        assert "必须是字符串" in str(exc_info.value)
    
    def test_is_port_success(self):
        """测试端口验证成功"""
        v = Validator().check("port", 8080).is_port()
        assert v.validate() == 8080
    
    def test_is_port_failure_out_of_range(self):
        """测试端口验证失败 - 超出范围"""
        v = Validator().check("port", 99999).is_port()
        with pytest.raises(ValidationError) as exc_info:
            v.validate()
        assert f"{MIN_PORT}-{MAX_PORT}" in str(exc_info.value)
    
    def test_is_port_failure_not_integer(self):
        """测试端口验证失败 - 非整数"""
        v = Validator().check("port", "8080").is_port()
        with pytest.raises(ValidationError) as exc_info:
            v.validate()
        assert "必须是整数" in str(exc_info.value)
    
    def test_is_timeout_success(self):
        """测试超时验证成功"""
        v = Validator().check("timeout", 30).is_timeout()
        assert v.validate() == 30
    
    def test_is_timeout_failure(self):
        """测试超时验证失败"""
        v = Validator().check("timeout", 999).is_timeout()
        with pytest.raises(ValidationError) as exc_info:
            v.validate()
        assert f"{MIN_TIMEOUT}-{MAX_TIMEOUT}" in str(exc_info.value)
    
    def test_is_retries_success(self):
        """测试重试次数验证成功"""
        v = Validator().check("retries", 3).is_retries()
        assert v.validate() == 3
    
    def test_is_interval_success(self):
        """测试间隔验证成功"""
        v = Validator().check("interval", 1.5).is_interval()
        assert v.validate() == 1.5
    
    def test_is_log_level_success(self):
        """测试日志级别验证成功"""
        v = Validator().check("level", "DEBUG").is_log_level()
        assert v.validate() == "DEBUG"
    
    def test_is_log_level_failure(self):
        """测试日志级别验证失败"""
        v = Validator().check("level", "INVALID").is_log_level()
        with pytest.raises(ValidationError) as exc_info:
            v.validate()
        assert "必须是以下值之一" in str(exc_info.value)
    
    def test_has_length_success(self):
        """测试长度验证成功"""
        v = Validator().check("field", "test").has_length(min_len=2, max_len=10)
        assert v.validate() == "test"
    
    def test_has_length_failure_too_short(self):
        """测试长度验证失败 - 太短"""
        v = Validator().check("field", "a").has_length(min_len=2, max_len=10)
        with pytest.raises(ValidationError) as exc_info:
            v.validate()
        assert "长度必须" in str(exc_info.value)
    
    def test_matches_pattern_success(self):
        """测试正则验证成功"""
        v = Validator().check("field", "test123").matches_pattern(r"^[a-z0-9]+$")
        assert v.validate() == "test123"
    
    def test_matches_pattern_failure(self):
        """测试正则验证失败"""
        v = Validator().check("field", "TEST").matches_pattern(r"^[a-z]+$")
        with pytest.raises(ValidationError) as exc_info:
            v.validate()
        assert "格式无效" in str(exc_info.value)
    
    def test_is_one_of_success(self):
        """测试枚举验证成功"""
        v = Validator().check("field", "a").is_one_of({"a", "b", "c"})
        assert v.validate() == "a"
    
    def test_is_one_of_failure(self):
        """测试枚举验证失败"""
        v = Validator().check("field", "d").is_one_of({"a", "b", "c"})
        with pytest.raises(ValidationError) as exc_info:
            v.validate()
        assert "必须是以下值之一" in str(exc_info.value)
    
    def test_custom_validator_success(self):
        """测试自定义验证成功"""
        v = Validator().check("field", 10).custom(lambda x: x > 5, "必须大于5")
        assert v.validate() == 10
    
    def test_custom_validator_failure(self):
        """测试自定义验证失败"""
        v = Validator().check("field", 3).custom(lambda x: x > 5, "必须大于5")
        with pytest.raises(ValidationError) as exc_info:
            v.validate()
        assert "必须大于5" in str(exc_info.value)
    
    def test_multiple_validators(self):
        """测试多个验证器链式调用"""
        v = (Validator()
             .check("port", 8080)
             .is_not_none()
             .is_integer()
             .is_port())
        assert v.validate() == 8080
    
    def test_multiple_errors(self):
        """测试多个错误"""
        v = (Validator()
             .check("field", None)
             .is_not_none()
             .is_string()
             .has_length(min_len=1))
        
        with pytest.raises(ValidationError) as exc_info:
            v.validate()
        
        # 应该报告第一个错误
        assert "不能为 None" in str(exc_info.value)


class TestValidatePort:
    """测试 validate_port 函数"""
    
    def test_valid_port(self):
        """测试有效端口"""
        assert validate_port(8080) == 8080
        assert validate_port(1) == 1
        assert validate_port(65535) == 65535
    
    def test_invalid_port_too_small(self):
        """测试端口过小"""
        with pytest.raises(ValidationError) as exc_info:
            validate_port(0)
        assert "1-65535" in str(exc_info.value)
    
    def test_invalid_port_too_large(self):
        """测试端口过大"""
        with pytest.raises(ValidationError) as exc_info:
            validate_port(65536)
        assert "1-65535" in str(exc_info.value)
    
    def test_invalid_port_not_integer(self):
        """测试非整数端口"""
        with pytest.raises(ValidationError) as exc_info:
            validate_port("8080")
        assert "必须是整数" in str(exc_info.value)


class TestValidateTimeout:
    """测试 validate_timeout 函数"""
    
    def test_valid_timeout(self):
        """测试有效超时"""
        assert validate_timeout(30) == 30.0
        assert validate_timeout(1.5) == 1.5
    
    def test_invalid_timeout(self):
        """测试无效超时"""
        with pytest.raises(ValidationError) as exc_info:
            validate_timeout(0)
        assert f"{MIN_TIMEOUT}-{MAX_TIMEOUT}" in str(exc_info.value)


class TestValidateRetries:
    """测试 validate_retries 函数"""
    
    def test_valid_retries(self):
        """测试有效重试次数"""
        assert validate_retries(3) == 3
        assert validate_retries(0) == 0
    
    def test_invalid_retries(self):
        """测试无效重试次数"""
        with pytest.raises(ValidationError) as exc_info:
            validate_retries(11)
        assert f"{MIN_RETRIES}-{MAX_RETRIES}" in str(exc_info.value)


class TestValidateInterval:
    """测试 validate_interval 函数"""
    
    def test_valid_interval(self):
        """测试有效间隔"""
        assert validate_interval(1.0) == 1.0
        assert validate_interval(0.5) == 0.5
    
    def test_invalid_interval(self):
        """测试无效间隔"""
        with pytest.raises(ValidationError) as exc_info:
            validate_interval(0.01)
        assert f"{MIN_CHECK_INTERVAL}-{MAX_CHECK_INTERVAL}" in str(exc_info.value)


class TestValidateLogLevel:
    """测试 validate_log_level 函数"""
    
    def test_valid_levels(self):
        """测试有效日志级别"""
        assert validate_log_level("DEBUG") == "DEBUG"
        assert validate_log_level("info") == "INFO"
        assert validate_log_level("Warning") == "WARNING"
    
    def test_invalid_level(self):
        """测试无效日志级别"""
        with pytest.raises(ValidationError) as exc_info:
            validate_log_level("VERBOSE")
        assert "必须是以下值之一" in str(exc_info.value)


class TestValidateNonEmptyString:
    """测试 validate_non_empty_string 函数"""
    
    def test_valid_string(self):
        """测试有效字符串"""
        assert validate_non_empty_string("test") == "test"
    
    def test_empty_string(self):
        """测试空字符串"""
        with pytest.raises(ValidationError) as exc_info:
            validate_non_empty_string("")
        assert "不能为空" in str(exc_info.value)
    
    def test_not_string(self):
        """测试非字符串"""
        with pytest.raises(ValidationError) as exc_info:
            validate_non_empty_string(123)
        assert "必须是字符串" in str(exc_info.value)


class TestValidateBoolean:
    """测试 validate_boolean 函数"""
    
    def test_true_values(self):
        """测试真值"""
        assert validate_boolean(True) is True
        assert validate_boolean("true") is True
        assert validate_boolean("TRUE") is True
        assert validate_boolean("1") is True
        assert validate_boolean("yes") is True
        assert validate_boolean("on") is True
        assert validate_boolean("enabled") is True
    
    def test_false_values(self):
        """测试假值"""
        assert validate_boolean(False) is False
        assert validate_boolean("false") is False
        assert validate_boolean("FALSE") is False
        assert validate_boolean("0") is False
        assert validate_boolean("no") is False
        assert validate_boolean("off") is False
        assert validate_boolean("disabled") is False
        assert validate_boolean("") is False
    
    def test_invalid_value(self):
        """测试无效值"""
        with pytest.raises(ValidationError) as exc_info:
            validate_boolean("maybe")
        assert "必须是布尔值" in str(exc_info.value)


class TestValidateRange:
    """测试 validate_range 函数"""
    
    def test_within_range(self):
        """测试在范围内"""
        assert validate_range(50, 0, 100) == 50
    
    def test_at_boundaries(self):
        """测试边界值"""
        assert validate_range(0, 0, 100) == 0
        assert validate_range(100, 0, 100) == 100
    
    def test_below_minimum(self):
        """测试低于最小值"""
        with pytest.raises(ValidationError) as exc_info:
            validate_range(-1, 0, 100)
        assert "不能小于" in str(exc_info.value)
    
    def test_above_maximum(self):
        """测试高于最大值"""
        with pytest.raises(ValidationError) as exc_info:
            validate_range(101, 0, 100)
        assert "不能大于" in str(exc_info.value)
    
    def test_only_minimum(self):
        """测试只有最小值"""
        assert validate_range(100, min_value=0) == 100
        with pytest.raises(ValidationError):
            validate_range(-1, min_value=0)
    
    def test_only_maximum(self):
        """测试只有最大值"""
        assert validate_range(50, max_value=100) == 50
        with pytest.raises(ValidationError):
            validate_range(101, max_value=100)


class TestValidateUrlScheme:
    """测试 validate_url_scheme 函数"""
    
    def test_valid_http(self):
        """测试有效 HTTP URL"""
        assert validate_url_scheme("http://example.com") == "http://example.com"
    
    def test_valid_https(self):
        """测试有效 HTTPS URL"""
        assert validate_url_scheme("https://example.com") == "https://example.com"
    
    def test_missing_scheme(self):
        """测试缺少协议"""
        with pytest.raises(ValidationError) as exc_info:
            validate_url_scheme("example.com")
        assert "缺少协议" in str(exc_info.value)
    
    def test_invalid_scheme(self):
        """测试无效协议"""
        with pytest.raises(ValidationError) as exc_info:
            validate_url_scheme("ftp://example.com")
        assert "不支持的协议" in str(exc_info.value)
    
    def test_custom_schemes(self):
        """测试自定义协议"""
        assert validate_url_scheme(
            "ftp://example.com",
            allowed_schemes={"ftp", "sftp"}
        ) == "ftp://example.com"


class TestCreateRangeValidator:
    """测试 create_range_validator 函数"""
    
    def test_positive_validator(self):
        """测试正数验证器"""
        validate_positive = create_range_validator(min_value=1)
        assert validate_positive(10) == 10
        with pytest.raises(ValidationError):
            validate_positive(0)
    
    def test_percentage_validator(self):
        """测试百分比验证器"""
        validate_percentage = create_range_validator(0, 100)
        assert validate_percentage(50) == 50
        with pytest.raises(ValidationError):
            validate_percentage(101)
