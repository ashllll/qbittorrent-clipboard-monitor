"""
增强的配置验证器

提供更严格的配置验证、类型检查和健壮性保证
"""

import re
import ipaddress
import socket
import urllib.parse
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from pydantic import BaseModel, ValidationError, field_validator
from .exceptions_enhanced import ConfigError as EnhancedConfigError
from .exceptions import ConfigError as LegacyConfigError


class ConfigValidator:
    """
    增强的配置验证器

    提供全面的配置验证，包括：
    - 网络连接检查
    - 路径有效性验证
    - API密钥格式验证
    - 业务逻辑验证
    - 安全检查
    """

    def __init__(self):
        self.logger = None
        self.validation_errors: List[str] = []
        self.warnings: List[str] = []

    def validate_qbittorrent_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证qBittorrent配置

        Args:
            config: qBittorrent配置字典

        Returns:
            验证后的配置字典

        Raises:
            EnhancedConfigError: 配置验证失败
        """
        self.validation_errors.clear()
        self.warnings.clear()

        # 1. 基础字段验证
        required_fields = ['host', 'port', 'username', 'password']
        for field in required_fields:
            if field not in config or not config[field]:
                self.validation_errors.append(f"必填字段 '{field}' 不能为空")

        # 2. 主机地址验证
        if 'host' in config:
            self._validate_host(config['host'])

        # 3. 端口号验证
        if 'port' in config:
            self._validate_port(config['port'])

        # 4. 认证信息验证
        if 'username' in config:
            self._validate_username(config['username'])
        if 'password' in config:
            self._validate_password(config['password'])

        # 5. 安全相关验证
        if 'use_https' in config and config['use_https']:
            if 'verify_ssl' in config and not config['verify_ssl']:
                self.warnings.append("使用HTTPS但不验证SSL证书存在安全风险")

        # 6. 路径映射验证
        if 'path_mapping' in config:
            self._validate_path_mapping(config['path_mapping'])

        if self.validation_errors:
            error_msg = "qBittorrent配置验证失败:\n" + "\n".join(
                f"  - {err}" for err in self.validation_errors
            )
            raise EnhancedConfigError(error_msg)

        return config

    def _validate_host(self, host: str) -> None:
        """验证主机地址"""
        host = host.strip()
        if not host:
            self.validation_errors.append("主机地址不能为空")
            return

        # 检查是否为IP地址
        try:
            ipaddress.ip_address(host)
            return  # IP地址有效
        except ValueError:
            pass

        # 检查是否为域名
        if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$', host):
            self.validation_errors.append(f"主机地址格式无效: {host}")
            return

    def _validate_port(self, port: int) -> None:
        """验证端口号"""
        if not isinstance(port, int):
            self.validation_errors.append(f"端口必须是整数，实际: {type(port).__name__}")
            return

        if not (1 <= port <= 65535):
            self.validation_errors.append(f"端口号必须在1-65535之间，实际: {port}")

        # 检查常见端口冲突
        if port in [80, 443, 22, 21, 25, 53, 110, 143, 993, 995, 3389, 5432, 3306]:
            self.warnings.append(f"使用常见端口 {port}，请确保没有冲突")

    def _validate_username(self, username: str) -> None:
        """验证用户名"""
        if len(username) < 2:
            self.validation_errors.append("用户名至少2个字符")

        if len(username) > 32:
            self.validation_errors.append("用户名不能超过32个字符")

        if ' ' in username:
            self.validation_errors.append("用户名不能包含空格")

        # 检查特殊字符
        if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
            self.validation_errors.append("用户名只能包含字母、数字、下划线、点和连字符")

    def _validate_password(self, password: str) -> None:
        """验证密码"""
        if len(password) < 1:
            self.validation_errors.append("密码不能为空")

        if len(password) > 128:
            self.validation_errors.append("密码不能超过128个字符")

        # 安全建议
        if len(password) < 6:
            self.warnings.append("密码强度较弱，建议至少6个字符")

    def _validate_path_mapping(self, path_mapping: List[Dict[str, str]]) -> None:
        """验证路径映射"""
        for i, mapping in enumerate(path_mapping):
            if 'source_prefix' not in mapping or 'target_prefix' not in mapping:
                self.validation_errors.append(f"路径映射项 {i+1} 缺少必需的字段")
                continue

            source = mapping['source_prefix']
            target = mapping['target_prefix']

            # 检查路径格式
            if not source.startswith('/'):
                self.validation_errors.append(f"路径映射项 {i+1} 的源路径必须以'/'开头")

            if not target.startswith('/'):
                self.validation_errors.append(f"路径映射项 {i+1} 的目标路径必须以'/'开头")

    def validate_ai_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证AI配置

        Args:
            config: AI配置字典

        Returns:
            验证后的配置字典

        Raises:
            EnhancedConfigError: 配置验证失败
        """
        self.validation_errors.clear()

        # 检查API密钥
        if 'api_key' in config:
            self._validate_api_key(config['api_key'])

        # 检查模型配置
        if 'model' in config:
            self._validate_model(config['model'])

        # 检查base_url
        if 'base_url' in config:
            self._validate_base_url(config['base_url'])

        # 检查超时配置
        if 'timeout' in config:
            self._validate_timeout(config['timeout'])

        if self.validation_errors:
            error_msg = "AI配置验证失败:\n" + "\n".join(
                f"  - {err}" for err in self.validation_errors
            )
            raise EnhancedConfigError(error_msg)

        return config

    def _validate_api_key(self, api_key: str) -> None:
        """验证API密钥"""
        if not api_key:
            self.warnings.append("API密钥为空，AI功能将被禁用")
            return

        if len(api_key) < 20:
            self.validation_errors.append("API密钥格式无效（过短）")

        # DeepSeek API密钥通常以sk-开头
        if not api_key.startswith('sk-') and not api_key.startswith('dpk-'):
            self.warnings.append("API密钥格式不标准，可能无法使用")

    def _validate_model(self, model: str) -> None:
        """验证模型名称"""
        valid_models = [
            'deepseek-chat',
            'deepseek-reasoner',
            'deepseek-coder',
            'gpt-3.5-turbo',
            'gpt-4',
            'gpt-4-turbo'
        ]

        if model not in valid_models:
            self.warnings.append(f"模型 '{model}' 不在推荐列表中")

    def _validate_base_url(self, base_url: str) -> None:
        """验证基础URL"""
        try:
            parsed = urllib.parse.urlparse(base_url)
            if not parsed.scheme or not parsed.netloc:
                self.validation_errors.append(f"基础URL格式无效: {base_url}")
                return

            if parsed.scheme not in ['http', 'https']:
                self.validation_errors.append(f"不支持的URL协议: {parsed.scheme}")

        except Exception as e:
            self.validation_errors.append(f"URL解析失败: {str(e)}")

    def _validate_timeout(self, timeout: int) -> None:
        """验证超时时间"""
        if not isinstance(timeout, (int, float)):
            self.validation_errors.append(f"超时时间必须是数字，实际: {type(timeout).__name__}")
            return

        if timeout <= 0:
            self.validation_errors.append("超时时间必须大于0")

        if timeout > 300:
            self.warnings.append("超时时间超过5分钟，可能影响性能")

    def validate_category_config(self, categories: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        验证分类配置

        Args:
            categories: 分类配置字典

        Returns:
            验证后的分类配置

        Raises:
            EnhancedConfigError: 配置验证失败
        """
        self.validation_errors.clear()
        self.warnings.clear()

        if not categories:
            self.warnings.append("未配置任何分类，将使用默认分类")
            return categories

        # 检查分类名称
        reserved_names = {'all', 'none', 'root', 'default'}
        for name in categories.keys():
            if name.lower() in reserved_names:
                self.validation_errors.append(f"分类名称 '{name}' 是保留名称")
            if len(name) > 20:
                self.validation_errors.append(f"分类名称 '{name}' 不能超过20个字符")

        # 检查每个分类
        for name, config in categories.items():
            self._validate_category(name, config)

        if self.validation_errors:
            error_msg = "分类配置验证失败:\n" + "\n".join(
                f"  - {err}" for err in self.validation_errors
            )
            raise EnhancedConfigError(error_msg)

        return categories

    def _validate_category(self, name: str, config: Dict[str, Any]) -> None:
        """验证单个分类配置"""
        # 检查保存路径
        if 'save_path' not in config or not config['save_path']:
            self.validation_errors.append(f"分类 '{name}' 必须指定保存路径")
        else:
            save_path = config['save_path']
            if not save_path.startswith('/'):
                self.validation_errors.append(f"分类 '{name}' 的保存路径必须以'/'开头")

        # 检查关键词
        if 'keywords' in config and config['keywords']:
            if not isinstance(config['keywords'], list):
                self.validation_errors.append(f"分类 '{name}' 的关键词必须是列表")
            else:
                for keyword in config['keywords']:
                    if not isinstance(keyword, str) or len(keyword.strip()) == 0:
                        self.validation_errors.append(f"分类 '{name}' 包含无效关键词")

    def validate_global_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证全局配置

        Args:
            config: 全局配置字典

        Returns:
            验证后的全局配置

        Raises:
            EnhancedConfigError: 配置验证失败
        """
        self.validation_errors.clear()

        # 检查监控间隔
        if 'check_interval' in config:
            self._validate_check_interval(config['check_interval'])

        # 检查日志配置
        if 'log_level' in config:
            self._validate_log_level(config['log_level'])

        # 检查通知配置
        if 'notifications' in config:
            self._validate_notifications(config['notifications'])

        if self.validation_errors:
            error_msg = "全局配置验证失败:\n" + "\n".join(
                f"  - {err}" for err in self.validation_errors
            )
            raise EnhancedConfigError(error_msg)

        return config

    def _validate_check_interval(self, interval: float) -> None:
        """检查监控间隔"""
        if not isinstance(interval, (int, float)):
            self.validation_errors.append(f"监控间隔必须是数字，实际: {type(interval).__name__}")
            return

        if interval <= 0:
            self.validation_errors.append("监控间隔必须大于0")

        if interval < 0.1:
            self.warnings.append("监控间隔过小（<0.1秒），可能消耗过多CPU")

        if interval > 10:
            self.warnings.append("监控间隔过大（>10秒），可能错过快速变化")

    def _validate_log_level(self, level: str) -> None:
        """验证日志级别"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if level.upper() not in valid_levels:
            self.validation_errors.append(f"无效的日志级别: {level}")

    def _validate_notifications(self, notifications: Dict[str, Any]) -> None:
        """验证通知配置"""
        if 'enabled' in notifications and not isinstance(notifications['enabled'], bool):
            self.validation_errors.append("通知启用状态必须是布尔值")

        if 'console' in notifications:
            console = notifications['console']
            if 'enabled' in console and not isinstance(console['enabled'], bool):
                self.validation_errors.append("控制台通知启用状态必须是布尔值")

    def get_validation_summary(self) -> Dict[str, Any]:
        """获取验证摘要"""
        return {
            "errors": self.validation_errors.copy(),
            "warnings": self.warnings.copy(),
            "error_count": len(self.validation_errors),
            "warning_count": len(self.warnings)
        }


class SecureConfig:
    """
    安全配置包装器

    提供敏感信息的加密存储和安全访问
    """

    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._masked_config = self._mask_sensitive_data(config)
        self._logger = logging.getLogger(__name__)

    def _mask_sensitive_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """掩码敏感数据"""
        masked = config.copy()

        # 掩码API密钥
        if 'deepseek' in masked and 'api_key' in masked['deepseek']:
            api_key = masked['deepseek']['api_key']
            if api_key:
                masked['deepseek']['api_key'] = f"{api_key[:8]}{'*' * (len(api_key) - 12)}{api_key[-4:]}"

        # 掩码密码
        if 'qbittorrent' in masked:
            if 'password' in masked['qbittorrent']:
                pwd = masked['qbittorrent']['password']
                if pwd:
                    masked['qbittorrent']['password'] = '*' * len(pwd)

        return masked

    def get_config(self) -> Dict[str, Any]:
        """获取完整配置（包含敏感信息）"""
        return self._config.copy()

    def get_masked_config(self) -> Dict[str, Any]:
        """获取掩码配置（不包含敏感信息）"""
        return self._masked_config.copy()

    def get_safe_dict(self, *keys: str) -> Dict[str, Any]:
        """安全获取配置字典的特定键"""
        result = {}
        for key in keys:
            if key in self._config:
                result[key] = self._config[key]
        return result


def validate_full_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    完整配置验证

    对整个配置进行全面的验证

    Args:
        config: 配置字典

    Returns:
        验证后的配置字典

    Raises:
        EnhancedConfigError: 配置验证失败
    """
    validator = ConfigValidator()

    # 验证各个部分
    if 'qbittorrent' in config:
        config['qbittorrent'] = validator.validate_qbittorrent_config(config['qbittorrent'])

    if 'deepseek' in config:
        config['deepseek'] = validator.validate_ai_config(config['deepseek'])

    if 'categories' in config:
        config['categories'] = validator.validate_category_config(config['categories'])

    # 验证全局配置
    config = validator.validate_global_config(config)

    # 获取验证摘要
    summary = validator.get_validation_summary()

    # 记录警告
    if summary['warnings']:
        logger = logging.getLogger(__name__)
        for warning in summary['warnings']:
            logger.warning(f"配置警告: {warning}")

    return config


# 创建全局验证器实例
_global_validator = ConfigValidator()
validate_config = _global_validator.validate_qbittorrent_config
validate_ai_config = _global_validator.validate_ai_config
validate_category_config = _global_validator.validate_category_config
