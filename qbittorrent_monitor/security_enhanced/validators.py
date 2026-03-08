"""安全验证器

提供额外的安全验证功能。
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Tuple, Optional, Dict, Pattern
from dataclasses import dataclass

from ..exceptions import ConfigError, QBMonitorError


@dataclass(frozen=True)
class SecurityPolicy:
    """安全策略配置"""
    max_magnet_length: int = 8192
    max_clipboard_size: int = 10 * 1024 * 1024  # 10MB
    max_path_depth: int = 10
    max_path_length: int = 4096
    max_keywords_per_category: int = 1000
    max_total_keywords: int = 5000
    enable_param_validation: bool = True
    enable_tracker_whitelist: bool = False
    allowed_trackers: Tuple[str, ...] = ()


class MagnetSecurityValidator:
    """磁力链接安全验证器"""
    
    # 标准磁力链接参数验证器
    PARAM_VALIDATORS: Dict[str, Pattern] = {
        'xt': re.compile(r'^urn:btih:[a-f0-9]{40}$', re.I),
        'dn': re.compile(r'^[\w\s\-_\.\[\](){}，!]{1,255}$'),
        'xl': re.compile(r'^\d{1,20}$'),
        'kt': re.compile(r'^[\w\s,]{1,200}$'),
        'mt': re.compile(r'^[\w/]{1,100}$'),
    }
    
    # Tracker URL 验证器
    TRACKER_VALIDATOR = re.compile(
        r'^https?://[a-z0-9][-a-z0-9.]*[a-z0-9]'
        r'(:\d{1,5})?'
        r'(/[\w\-./]*)?$',
        re.I
    )
    
    VALID_PARAMS = {'xt', 'dn', 'tr', 'xl', 'as', 'xs', 'kt', 'mt', 'so'}
    
    @classmethod
    def validate(
        cls,
        magnet: str,
        policy: Optional[SecurityPolicy] = None
    ) -> Tuple[bool, Optional[str]]:
        """全面验证磁力链接安全性"""
        policy = policy or SecurityPolicy()
        
        # 基础长度检查
        if len(magnet) > policy.max_magnet_length:
            return False, f"磁力链接过长: {len(magnet)} > {policy.max_magnet_length}"
        
        # 解析参数
        try:
            parsed = urllib.parse.urlparse(magnet)
            params = urllib.parse.parse_qs(parsed.query)
        except Exception as e:
            return False, f"URL解析失败: {e}"
        
        # 验证 xt 参数必须存在
        if 'xt' not in params:
            return False, "缺少必需的 xt 参数"
        
        if not policy.enable_param_validation:
            return True, None
        
        # 验证每个参数
        for key, values in params.items():
            if key not in cls.VALID_PARAMS:
                return False, f"不支持的参数: {key}"
            
            # 验证参数值
            validator = cls.PARAM_VALIDATORS.get(key)
            if validator:
                for value in values:
                    decoded = urllib.parse.unquote(value)
                    if not validator.match(decoded):
                        return False, f"参数 {key} 值不合法: {decoded[:50]}..."
            
            # 特殊处理 tracker 列表
            if key == 'tr' and policy.enable_tracker_whitelist:
                for tracker_url in values:
                    decoded = urllib.parse.unquote(tracker_url)
                    if not cls.TRACKER_VALIDATOR.match(decoded):
                        return False, f"Tracker URL 格式错误: {decoded[:50]}..."
        
        return True, None


class PathSecurityValidator:
    """路径安全验证器"""
    
    DANGEROUS_PATTERNS = [
        re.compile(r'\.\.[\\/]'),
        re.compile(r'[\\/]\.\.'),
        re.compile(r'^\.\.'),
        re.compile(r'\.\.$'),
        re.compile(r'[~]'),
        re.compile(r'\$\w+'),
        re.compile(r'`[^`]*`'),
        re.compile(r'\$\([^)]*\)'),
    ]
    
    @classmethod
    def validate(
        cls,
        path: str,
        name: str = "path",
        policy: Optional[SecurityPolicy] = None
    ) -> Tuple[bool, Optional[str]]:
        """验证路径安全性"""
        policy = policy or SecurityPolicy()
        
        if not path:
            return False, f"{name} 不能为空"
        
        # 长度检查
        if len(path) > policy.max_path_length:
            return False, f"{name} 过长: {len(path)} > {policy.max_path_length}"
        
        # 危险模式检查
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(path):
                return False, f"{name} 包含危险序列"
        
        # 深度检查
        depth = len([p for p in path.replace('\\', '/').split('/') if p])
        if depth > policy.max_path_depth:
            return False, f"{name} 层级过多: {depth} > {policy.max_path_depth}"
        
        return True, None


class LogSecuritySanitizer:
    """日志安全清理器"""
    
    SENSITIVE_PATTERNS = [
        (re.compile(r'(password["\']?\s*[:=]\s*["\']?)[^\s"\']{3,}', re.I), r'\1***'),
        (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)[\w\-]{8,}', re.I), r'\1***'),
        (re.compile(r'(token["\']?\s*[:=]\s*["\']?)[\w\-\.]{10,}', re.I), r'\1***'),
        (re.compile(r'(bearer\s+)([\w\-\.]{10,})', re.I), r'\1***'),
        (re.compile(r'(://[^:]+:)([^@]+)(@)'), r'\1***\3'),
        (re.compile(r'(magnet:\?xt=urn:btih:[a-f0-9]{8})[a-f0-9]{32}', re.I), r'\1***'),
    ]
    
    @classmethod
    def sanitize(cls, text: str) -> str:
        """清理文本中的敏感信息"""
        if not isinstance(text, str):
            return str(text)
        
        result = text
        for pattern, replacement in cls.SENSITIVE_PATTERNS:
            result = pattern.sub(replacement, result)
        
        return result
    
    @classmethod
    def safe_format(cls, template: str, *args) -> str:
        """安全的字符串格式化"""
        # 转义所有 %
        safe_args = tuple(
            str(arg).replace('%', '%%') if isinstance(arg, str) else arg
            for arg in args
        )
        return template % safe_args


def sanitize_exception(exc: Exception) -> str:
    """清理异常信息中的敏感数据"""
    exc_str = str(exc)
    
    # 移除敏感模式
    patterns = [
        (re.compile(r'(password["\']?\s*[:=]\s*["\']?)[^\s"\']+', re.I), r'\1***'),
        (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)[^\s"\']+', re.I), r'\1***'),
        (re.compile(r'(/[^/]+/){0,3}\.config/[^/]+'), r'/.../.config/***'),
        (re.compile(r'(/[^/]+/){0,3}\.local/[^/]+'), r'/.../.local/***'),
    ]
    
    for pattern, replacement in patterns:
        exc_str = re.sub(pattern, replacement, exc_str, flags=re.I)
    
    return exc_str
