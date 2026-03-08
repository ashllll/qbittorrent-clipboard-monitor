"""
日志增强模块 - 安全脱敏和审计

提供增强的敏感信息过滤、内存清理、加密存储等功能。
"""

import re
import logging
import logging.handlers
import hashlib
import secrets
import time
from typing import Pattern, List, Tuple, Optional, Any, Union, Dict, Set
from pathlib import Path


# ============ 增强的敏感信息过滤器 ============

class EnhancedSensitiveDataFilter(logging.Filter):
    """
    增强版敏感信息过滤器
    
    提供更全面的敏感信息检测和过滤功能。
    """
    
    # 敏感字段名称模式（扩展）
    SENSITIVE_FIELD_PATTERNS: List[Tuple[Pattern[str], str]] = [
        # API密钥（各种格式）
        (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([\w\-]{10,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(api[_-]?secret["\']?\s*[:=]\s*["\']?)([^\s"\']{8,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(sk-[a-zA-Z0-9]{20,})', re.IGNORECASE), r'sk-***'),
        (re.compile(r'(Bearer\s+)([a-zA-Z0-9_\-\.]+)', re.IGNORECASE), r'\1***'),
        
        # 密码（多种格式）
        (re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^\s"\']{1,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(passwd["\']?\s*[:=]\s*["\']?)([^\s"\']{1,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(pwd["\']?\s*[:=]\s*["\']?)([^\s"\']{1,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'("password"\s*:\s*")([^"]*)(")', re.IGNORECASE), r'\1***\3'),
        
        # 令牌
        (re.compile(r'(token["\']?\s*[:=]\s*["\']?)([\w\-\.]{10,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(access[_-]?token["\']?\s*[:=]\s*["\']?)([^\s"\']{10,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(refresh[_-]?token["\']?\s*[:=]\s*["\']?)([^\s"\']{10,})', re.IGNORECASE), r'\1***'),
        
        # 认证头
        (re.compile(r'(Authorization["\']?\s*[:=]\s*["\']?\s*Bearer\s+)([^\s"\']+)', re.IGNORECASE), r'\1***'),
        (re.compile(r'(Authorization["\']?\s*[:=]\s*["\']?\s*Basic\s+)([^\s"\']+)', re.IGNORECASE), r'\1***'),
        
        # 磁力链接hash（保留前8位）
        (re.compile(r'(magnet:\?xt=urn:btih:)([a-f0-9]{8})[a-f0-9]{32}', re.IGNORECASE), r'\1\2***'),
        (re.compile(r'(magnet:\?xt=urn:btih:)([a-f0-9]{8})[a-z2-7]{24}', re.IGNORECASE), r'\1\2***'),
        (re.compile(r'(btih:)([a-f0-9]{8})[a-f0-9]{32}', re.IGNORECASE), r'\1\2***'),
        
        # 私钥
        (re.compile(r'(private[_-]?key["\']?\s*[:=]\s*["\']?)([^\s"\']{10,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(secret["\']?\s*[:=]\s*["\']?)([^\s"\']{3,})', re.IGNORECASE), r'\1***'),
        
        # 数据库连接字符串
        (re.compile(r'(://[^:]+:)([^@]+)(@)', re.IGNORECASE), r'\1***\3'),
        
        # Cookie
        (re.compile(r'(Cookie:\s*.*)(session|auth|sid|token)=([^;\s]{5,})', re.IGNORECASE), r'\1\2=***'),
        
        # SSH密钥
        (re.compile(r'(ssh-[a-z]+\s+)([A-Za-z0-9+/=]{20,})', re.IGNORECASE), r'\1***'),
        (re.compile(r'(-----BEGIN [A-Z ]+-----)([A-Za-z0-9+/=\s]+)(-----END [A-Z ]+-----)', re.IGNORECASE), r'\1***\3'),
        
        # URL中的认证信息
        (re.compile(r'(https?://)([^:]+):([^@]+)@', re.IGNORECASE), r'\1\2:***@'),
        
        # 环境变量中的敏感信息
        (re.compile(r'(QBIT_PASSWORD|AI_API_KEY|SECRET_KEY)\s*=\s*(\S+)', re.IGNORECASE), r'\1=***'),
        
        # JWT令牌
        (re.compile(r'(eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*)\.([a-zA-Z0-9_-]*)', re.IGNORECASE), r'\1.***'),
    ]
    
    # 完全过滤的敏感键
    SENSITIVE_KEYS: Set[str] = {
        'password', 'passwd', 'pwd', 'secret', 'api_key', 'apikey',
        'api_secret', 'apisecret', 'token', 'access_token', 'accesstoken',
        'refresh_token', 'refreshtoken', 'private_key', 'privatekey',
        'auth_token', 'authtoken', 'bearer', 'credential', 'credentials',
        'session', 'cookie', 'sid', 'csrf_token', 'xsrf_token',
        'jwt', 'auth', 'authorization', 'key', 'signature'
    }
    
    # 部分脱敏的字段（保留部分信息）
    PARTIAL_MASK_KEYS = {
        'username', 'user', 'email', 'host', 'ip'
    }
    
    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self.patterns = self.SENSITIVE_FIELD_PATTERNS.copy()
        self.mask_string = "***"
        self.partial_mask_visible_chars = 3
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录中的敏感信息
        
        Args:
            record: 日志记录对象
            
        Returns:
            True（始终通过，但内容可能被修改）
        """
        # 处理消息
        if isinstance(record.msg, str):
            record.msg = self._filter_text(record.msg)
        
        # 安全处理参数
        if record.args:
            try:
                # 过滤参数
                safe_args = tuple(
                    self._filter_text(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
                record.args = safe_args
            except Exception:
                pass
        
        # 过滤异常信息
        if record.exc_info and record.exc_info[1]:
            exc_str = str(record.exc_info[1])
            filtered_exc = self._filter_text(exc_str)
            if filtered_exc != exc_str:
                try:
                    record.exc_info = (
                        record.exc_info[0],
                        record.exc_info[0](filtered_exc),
                        record.exc_info[2]
                    )
                except Exception:
                    pass
        
        return True
    
    def _filter_text(self, text: str) -> str:
        """
        过滤文本中的敏感数据
        
        Args:
            text: 原始文本
            
        Returns:
            过滤后的文本
        """
        if not isinstance(text, str):
            return str(text)
        
        filtered_text = text
        for pattern, replacement in self.patterns:
            filtered_text = pattern.sub(replacement, filtered_text)
        
        return filtered_text
    
    def _partial_mask(self, value: str) -> str:
        """部分脱敏（保留前N个字符）"""
        if not value or len(value) <= self.partial_mask_visible_chars * 2:
            return self.mask_string
        
        visible = self.partial_mask_visible_chars
        return f"{value[:visible]}{self.mask_string}{value[-visible:]}"
    
    @classmethod
    def filter_dict(
        cls,
        data: Any,
        mask: str = "***",
        partial_mask: bool = True
    ) -> Any:
        """
        递归过滤字典中的敏感字段
        
        Args:
            data: 原始数据
            mask: 脱敏字符串
            partial_mask: 是否对部分字段使用部分脱敏
            
        Returns:
            过滤后的数据
        """
        if not isinstance(data, dict):
            return data
        
        filtered: Dict[str, Any] = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            if any(s in key_lower for s in cls.SENSITIVE_KEYS):
                # 完全脱敏
                filtered[key] = mask
            elif partial_mask and any(s in key_lower for s in cls.PARTIAL_MASK_KEYS):
                # 部分脱敏
                if isinstance(value, str) and len(value) > 6:
                    filtered[key] = f"{value[:3]}...{value[-3:]}"
                else:
                    filtered[key] = value
            elif isinstance(value, dict):
                filtered[key] = cls.filter_dict(value, mask, partial_mask)
            elif isinstance(value, list):
                filtered[key] = [
                    cls.filter_dict(item, mask, partial_mask) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                filtered[key] = value
        
        return filtered
    
    @classmethod
    def filter_string_list(cls, items: List[str]) -> List[str]:
        """过滤字符串列表中的敏感信息"""
        filter_instance = cls()
        return [filter_instance._filter_text(item) for item in items]


class SecureFormatter(logging.Formatter):
    """
    安全的日志格式化器
    
    自动应用敏感信息过滤的格式化器。
    """
    
    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        validate: bool = True
    ) -> None:
        super().__init__(fmt, datefmt, validate=validate)
        self._filter = EnhancedSensitiveDataFilter()
    
    def format(self, record: logging.LogRecord) -> str:
        # 先应用过滤器
        self._filter.filter(record)
        return super().format(record)


# ============ 内存敏感数据管理 ============

class SecureString:
    """
    安全字符串
    
    尝试提供比普通字符串更安全的敏感数据存储。
    注意：由于Python字符串的不可变性，这只是一个尽力而为的实现。
    """
    
    def __init__(self, value: str):
        self._value = value
        self._hash = hashlib.sha256(value.encode()).hexdigest()[:16]
        self._access_count = 0
    
    def get(self) -> str:
        """获取值（计数访问）"""
        self._access_count += 1
        return self._value
    
    def __str__(self) -> str:
        return self.masked
    
    def __repr__(self) -> str:
        return f"SecureString(hash={self._hash}, accesses={self._access_count})"
    
    @property
    def masked(self) -> str:
        """获取脱敏表示"""
        if len(self._value) <= 6:
            return "***"
        return f"{self._value[:3]}***{self._value[-3:]}"
    
    @property
    def hash(self) -> str:
        """获取值的哈希（用于比较）"""
        return self._hash
    
    def clear(self) -> None:
        """尝试清除值"""
        # Python字符串不可变，这里只是标记
        self._value = ""
    
    def __del__(self):
        """析构时清理"""
        self.clear()


class SecureConfigStore:
    """
    安全配置存储
    
    提供敏感配置的内存存储和管理。
    """
    
    def __init__(self):
        self._store: Dict[str, SecureString] = {}
        self._access_log: List[Tuple[str, float]] = []
    
    def set(self, key: str, value: str) -> None:
        """设置敏感值"""
        self._store[key] = SecureString(value)
        self._access_log.append((f"SET:{key}", time.time()))
    
    def get(self, key: str) -> Optional[str]:
        """获取敏感值"""
        secure = self._store.get(key)
        if secure:
            self._access_log.append((f"GET:{key}", time.time()))
            return secure.get()
        return None
    
    def get_masked(self, key: str) -> Optional[str]:
        """获取脱敏值"""
        secure = self._store.get(key)
        return secure.masked if secure else None
    
    def remove(self, key: str) -> bool:
        """移除敏感值"""
        if key in self._store:
            self._store[key].clear()
            del self._store[key]
            self._access_log.append((f"REMOVE:{key}", time.time()))
            return True
        return False
    
    def clear_all(self) -> None:
        """清除所有敏感值"""
        for key in list(self._store.keys()):
            self._store[key].clear()
        self._store.clear()
        self._access_log.append(("CLEAR_ALL", time.time()))
    
    def has_key(self, key: str) -> bool:
        """检查是否包含键"""
        return key in self._store
    
    def get_keys(self) -> List[str]:
        """获取所有键（敏感信息不包含值）"""
        return list(self._store.keys())


# ============ 审计日志 ============

class AuditLogger:
    """
    审计日志记录器
    
    记录安全相关事件，支持结构化日志输出。
    """
    
    # 事件类型
    EVENT_TYPES = {
        'AUTH_SUCCESS',      # 认证成功
        'AUTH_FAILURE',      # 认证失败
        'ACCESS_DENIED',     # 访问被拒绝
        'VALIDATION_ERROR',  # 验证错误
        'RATE_LIMITED',      # 触发速率限制
        'CIRCUIT_OPENED',    # 熔断器打开
        'CONFIG_CHANGE',     # 配置变更
        'SENSITIVE_ACCESS',  # 敏感数据访问
    }
    
    def __init__(self, logger_name: str = "audit"):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        self._filter = EnhancedSensitiveDataFilter()
    
    def log(
        self,
        event_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        level: int = logging.INFO
    ) -> None:
        """
        记录审计事件
        
        Args:
            event_type: 事件类型
            message: 事件描述
            details: 详细信息
            level: 日志级别
        """
        import time
        
        if event_type not in self.EVENT_TYPES:
            event_type = "UNKNOWN"
        
        # 构建审计记录
        audit_record = {
            'timestamp': time.time(),
            'event_type': event_type,
            'message': message,
            'details': EnhancedSensitiveDataFilter.filter_dict(details or {})
        }
        
        # 格式化并记录
        formatted = f"[AUDIT:{event_type}] {message} | Details: {audit_record['details']}"
        self.logger.log(level, formatted)
    
    def auth_success(self, user: str, source: str = "unknown") -> None:
        """记录认证成功"""
        self.log('AUTH_SUCCESS', f'User {user} authenticated', {'user': user, 'source': source})
    
    def auth_failure(self, user: str, reason: str, source: str = "unknown") -> None:
        """记录认证失败"""
        self.log('AUTH_FAILURE', f'User {user} authentication failed: {reason}', 
                 {'user': user, 'reason': reason, 'source': source}, logging.WARNING)
    
    def access_denied(self, resource: str, user: str = "unknown", reason: str = "") -> None:
        """记录访问被拒绝"""
        self.log('ACCESS_DENIED', f'Access to {resource} denied', 
                 {'resource': resource, 'user': user, 'reason': reason}, logging.WARNING)
    
    def validation_error(self, field: str, error: str) -> None:
        """记录验证错误"""
        self.log('VALIDATION_ERROR', f'Validation failed for {field}: {error}',
                 {'field': field, 'error': error}, logging.WARNING)
    
    def rate_limited(self, key: str, limit: int, window: float) -> None:
        """记录速率限制触发"""
        self.log('RATE_LIMITED', f'Rate limit exceeded for {key}',
                 {'key': key, 'limit': limit, 'window': window}, logging.WARNING)
    
    def circuit_opened(self, name: str, failures: int) -> None:
        """记录熔断器打开"""
        self.log('CIRCUIT_OPENED', f'Circuit breaker {name} opened after {failures} failures',
                 {'name': name, 'failures': failures}, logging.ERROR)


# ============ 安全日志处理器 ============

class SecureRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    安全的轮转文件处理器
    
    确保日志文件具有安全的权限设置。
    """
    
    def __init__(
        self,
        filename: Union[str, Path],
        mode: str = 'a',
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: Optional[str] = None,
        delay: bool = False
    ):
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        self._set_secure_permissions()
    
    def _set_secure_permissions(self) -> None:
        """设置安全的文件权限"""
        import os
        import stat
        
        try:
            # 设置文件权限为仅所有者可读写 (0o600)
            os.chmod(self.baseFilename, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass
    
    def doRollover(self) -> None:
        """轮转时保持安全权限"""
        super().doRollover()
        self._set_secure_permissions()


def setup_secure_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    enable_audit: bool = True
) -> Tuple[logging.Logger, Optional[AuditLogger]]:
    """
    设置安全的日志系统
    
    Args:
        level: 日志级别
        log_file: 日志文件路径
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的备份文件数量
        enable_audit: 是否启用审计日志
        
    Returns:
        Tuple[Logger, Optional[AuditLogger]]: (主日志记录器, 审计日志记录器)
    """
    # 配置根记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有处理器
    root_logger.handlers = []
    
    # 创建安全格式化器
    formatter = SecureFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 创建并添加敏感信息过滤器
    sensitive_filter = EnhancedSensitiveDataFilter()
    root_logger.addFilter(sensitive_filter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper()))
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)
    root_logger.addHandler(console_handler)
    
    # 文件处理器（如果指定）
    if log_file:
        file_handler = SecureRotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        root_logger.addHandler(file_handler)
    
    # 审计日志
    audit_logger = AuditLogger() if enable_audit else None
    
    return root_logger, audit_logger


# ============ 实用函数 ============

def sanitize_for_log(obj: Any) -> str:
    """
    将对象转换为安全的日志字符串
    
    Args:
        obj: 任意对象
        
    Returns:
        安全的字符串表示
    """
    if obj is None:
        return "None"
    
    text = str(obj)
    
    # 应用敏感信息过滤
    filter_instance = EnhancedSensitiveDataFilter()
    return filter_instance._filter_text(text)


def create_secure_log_filter() -> EnhancedSensitiveDataFilter:
    """创建敏感信息过滤器实例"""
    return EnhancedSensitiveDataFilter()


def mask_config_dict(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    脱敏配置字典
    
    Args:
        config: 配置字典
        
    Returns:
        脱敏后的配置字典
    """
    return EnhancedSensitiveDataFilter.filter_dict(config, partial_mask=True)


# ============ 向后兼容 ============

# 保持与旧logging_filters模块的兼容
SensitiveDataFilter = EnhancedSensitiveDataFilter
RedactingFormatter = SecureFormatter
setup_sensitive_logging = setup_secure_logging
