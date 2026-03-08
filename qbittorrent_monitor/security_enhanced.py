"""
安全工具模块 - 增强版

提供全面的安全验证、输入清理、DoS防护、速率限制等功能。
遵循 OWASP 安全最佳实践。
"""

import re
import os
import hashlib
import secrets
import time
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Set, Any, Callable
from urllib.parse import urlparse, unquote
from dataclasses import dataclass, field
from enum import Enum

from .exceptions import ConfigError, QBMonitorError


# ============ 磁力链接安全增强 ============

class MagnetValidationError(QBMonitorError):
    """磁力链接验证错误"""
    pass


# 允许的磁力链接参数白名单（严格按照 BEP-0009 和扩展）
ALLOWED_MAGNET_PARAMS: Set[str] = {
    'xt',   # 精确主题（eXact Topic）- 必需
    'dn',   # 显示名称（Display Name）
    'tr',   # Tracker URL
    'xl',   # 精确长度（eXact Length）
    'as',   # 可接受来源（Acceptable Source）
    'xs',   # 精确来源（eXact Source）
    'kt',   # 关键字主题（Keyword Topic）
    'mt',   # 清单主题（Manifest Topic）
    'so',   # 超级种子（Superseed Only）
}

# 磁力链接hash正则模式 - 40位十六进制
MAGNET_BTIH_PATTERN = re.compile(
    r'^magnet:\?xt=urn:btih:[a-f0-9]{40}',
    re.IGNORECASE
)

# 磁力链接hash提取模式 - 支持40位十六进制和32位base32
BTIH_HEX_PATTERN = re.compile(r'btih:([a-f0-9]{40})', re.IGNORECASE)
BTIH_BASE32_PATTERN = re.compile(r'btih:([a-z2-7]{32})', re.IGNORECASE)

# 磁力链接参数验证模式
MAGNET_PARAM_PATTERN = re.compile(r'([a-zA-Z][a-zA-Z0-9]*)=', re.ASCII)

# URL安全字符集（RFC 3986）
URL_SAFE_CHARS = re.compile(r'^[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=]+$', re.ASCII)

# 控制字符检测
CONTROL_CHARS = re.compile(r'[\x00-\x1f\x7f]')

# 磁力链接长度限制
MIN_MAGNET_LENGTH = 50          # 最小长度（magnet:?xt=urn:btih: + 40位hash）
MAX_MAGNET_LENGTH = 4096        # 最大长度（防止DoS）
MAX_MAGNET_PARAMS = 50          # 最大参数数量
MAX_PARAM_VALUE_LENGTH = 2048   # 单个参数值最大长度
MAX_TRACKER_URLS = 20           # 最大tracker数量


def validate_magnet_strict(magnet: str) -> Tuple[bool, Optional[str]]:
    """
    严格验证磁力链接的有效性（增强版）
    
    验证内容包括：
    - 格式正确性
    - 参数白名单
    - 长度限制
    - 特殊字符过滤
    - 编码安全性
    
    Args:
        magnet: 磁力链接字符串
        
    Returns:
        Tuple[bool, Optional[str]]: (是否有效, 错误信息)
    """
    if not isinstance(magnet, str):
        return False, "磁力链接必须是字符串类型"
    
    if not magnet:
        return False, "磁力链接为空"
    
    # 长度检查
    if len(magnet) < MIN_MAGNET_LENGTH:
        return False, f"磁力链接过短（最小{MIN_MAGNET_LENGTH}字符）"
    
    if len(magnet) > MAX_MAGNET_LENGTH:
        return False, f"磁力链接过长（最大{MAX_MAGNET_LENGTH}字符）"
    
    # 必须以 magnet:? 开头（不区分大小写）
    if not magnet.lower().startswith("magnet:?"):
        return False, "磁力链接格式错误：必须以magnet:?开头"
    
    # 提取查询部分
    query_part = magnet[8:]  # 移除 "magnet:?"
    
    # 检查参数数量
    param_count = query_part.count('&') + 1
    if param_count > MAX_MAGNET_PARAMS:
        return False, f"参数数量过多（最大{MAX_MAGNET_PARAMS}个）"
    
    # 验证 xt 参数（必需）
    if 'xt=' not in query_part:
        return False, "磁力链接缺少必需的xt参数"
    
    # 验证hash格式
    hex_match = BTIH_HEX_PATTERN.search(magnet)
    base32_match = BTIH_BASE32_PATTERN.search(magnet)
    
    if not hex_match and not base32_match:
        return False, "磁力链接缺少有效的btih hash（需要40位十六进制或32位base32）"
    
    # 验证参数名白名单
    param_names = MAGNET_PARAM_PATTERN.findall(query_part)
    invalid_params = set(param_names) - ALLOWED_MAGNET_PARAMS
    if invalid_params:
        return False, f"不支持的参数: {', '.join(invalid_params)}"
    
    # 验证URL编码安全性
    try:
        decoded = unquote(magnet)
        # 检查解码后是否包含控制字符
        if CONTROL_CHARS.search(decoded):
            return False, "磁力链接包含非法控制字符"
    except Exception as e:
        return False, f"磁力链接编码错误: {e}"
    
    # 验证只包含URL安全字符
    if not URL_SAFE_CHARS.match(magnet):
        return False, "磁力链接包含非法字符"
    
    # 验证tr参数（tracker URL）
    if 'tr=' in magnet:
        tracker_count = magnet.count('tr=')
        if tracker_count > MAX_TRACKER_URLS:
            return False, f"tracker数量过多（最大{MAX_TRACKER_URLS}个）"
    
    # 验证参数值长度
    for param_match in MAGNET_PARAM_PATTERN.finditer(query_part):
        param_end = param_match.end()
        next_amp = query_part.find('&', param_end)
        if next_amp == -1:
            value = query_part[param_end:]
        else:
            value = query_part[param_end:next_amp]
        
        if len(value) > MAX_PARAM_VALUE_LENGTH:
            return False, f"参数值过长（最大{MAX_PARAM_VALUE_LENGTH}字符）"
    
    return True, None


def sanitize_magnet_strict(magnet: str) -> str:
    """
    严格清理磁力链接（增强版）
    
    Args:
        magnet: 原始磁力链接
        
    Returns:
        清理后的磁力链接
    """
    if not isinstance(magnet, str):
        return ""
    
    # 限制长度
    magnet = magnet[:MAX_MAGNET_LENGTH]
    
    # 移除所有控制字符
    magnet = ''.join(c for c in magnet if ord(c) >= 32 and ord(c) != 127)
    
    # 规范化协议部分
    if magnet.lower().startswith('magnet:?'):
        magnet = 'magnet:?' + magnet[8:]
    
    # 移除HTML标签（防止XSS）
    magnet = re.sub(r'<[^>]+>', '', magnet)
    
    return magnet.strip()


def extract_magnet_hash_strict(magnet: str) -> Optional[str]:
    """
    安全地提取磁力链接hash（增强版）
    
    Args:
        magnet: 磁力链接
        
    Returns:
        hash字符串（40位十六进制小写或32位base32小写），无效时返回None
    """
    is_valid, error = validate_magnet_strict(magnet)
    if not is_valid:
        return None
    
    # 优先匹配40位十六进制
    match = BTIH_HEX_PATTERN.search(magnet)
    if match:
        return match.group(1).lower()
    
    # 匹配32位base32
    match = BTIH_BASE32_PATTERN.search(magnet)
    if match:
        return match.group(1).lower()
    
    return None


def is_valid_magnet_strict(magnet: str) -> bool:
    """快速检查磁力链接是否有效（增强版）"""
    is_valid, _ = validate_magnet_strict(magnet)
    return is_valid


# ============ 路径安全增强 ============

class PathValidationError(QBMonitorError):
    """路径验证错误"""
    pass


# 路径遍历危险模式
PATH_TRAVERSAL_PATTERNS = [
    re.compile(r'\.\.[\/]'),      # ../ 或 ..\
    re.compile(r'[\/]\.\.'),      # /.. 或 \..
    re.compile(r'\.\.\Z'),        # 以 .. 结尾
    re.compile(r'^\.\.'),         # 以 .. 开头
]

# 非法路径字符（Windows和Unix）
ILLEGAL_PATH_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')

# Windows保留名称
WINDOWS_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
}

# 路径长度限制
MAX_PATH_LENGTH = 4096
MAX_PATH_DEPTH = 32  # 最大目录深度
MAX_FILENAME_LENGTH = 255
MIN_PATH_LENGTH = 1

# 允许的根目录列表（可配置）
ALLOWED_ROOT_PATHS: List[str] = []


def validate_save_path_strict(
    path: str,
    name: str = "save_path",
    allow_absolute: bool = True,
    max_depth: int = MAX_PATH_DEPTH
) -> None:
    """
    严格验证保存路径的安全性（增强版）
    
    Args:
        path: 路径字符串
        name: 配置项名称（用于错误信息）
        allow_absolute: 是否允许绝对路径
        max_depth: 最大目录深度
        
    Raises:
        PathValidationError: 当路径存在安全风险时
    """
    if not isinstance(path, str):
        raise PathValidationError(f"{name} 必须是字符串类型")
    
    if not path:
        raise PathValidationError(f"{name} 不能为空")
    
    path = path.strip()
    
    if not path:
        raise PathValidationError(f"{name} 不能为空字符串")
    
    # 长度检查
    if len(path) > MAX_PATH_LENGTH:
        raise PathValidationError(
            f"{name} 过长（最大{MAX_PATH_LENGTH}字符）"
        )
    
    if len(path) < MIN_PATH_LENGTH:
        raise PathValidationError(
            f"{name} 过短（最小{MIN_PATH_LENGTH}字符）"
        )
    
    # 路径遍历检查
    normalized_path = path.replace('\\', '/')
    for pattern in PATH_TRAVERSAL_PATTERNS:
        if pattern.search(normalized_path):
            raise PathValidationError(
                f"{name} 包含不安全的路径遍历序列"
            )
    
    # 检查 ../ 通过规范化
    try:
        resolved = Path(path).resolve()
        # 检查解析后的路径是否与原始路径一致（防止遍历）
        if '..' in str(resolved) and '..' not in path:
            pass  # 这是正常的绝对路径转换
    except Exception:
        raise PathValidationError(f"{name} 路径解析失败")
    
    # 深度检查
    path_parts = [p for p in normalized_path.split('/') if p and p != '.']
    if len(path_parts) > max_depth:
        raise PathValidationError(
            f"{name} 目录深度超过限制（最大{max_depth}层）"
        )
    
    # 非法字符检查
    if ILLEGAL_PATH_CHARS.search(path):
        raise PathValidationError(
            f"{name} 包含非法字符"
        )
    
    # Windows保留名称检查
    for part in path_parts:
        base_name = part.split('.')[0].upper()
        if base_name in WINDOWS_RESERVED_NAMES:
            raise PathValidationError(
                f"{name} 包含Windows保留名称: {part}"
            )
    
    # 绝对路径检查
    if not allow_absolute:
        if path.startswith('/') or (len(path) > 1 and path[1] == ':'):
            raise PathValidationError(
                f"{name} 不允许使用绝对路径"
            )
    
    # 允许的根目录检查
    if ALLOWED_ROOT_PATHS:
        is_allowed = any(
            normalized_path.startswith(allowed.replace('\\', '/'))
            for allowed in ALLOWED_ROOT_PATHS
        )
        if not is_allowed:
            raise PathValidationError(
                f"{name} 不在允许的根目录范围内"
            )


def validate_path_depth(path: str, max_depth: int = MAX_PATH_DEPTH) -> bool:
    """
    验证路径深度是否在限制内
    
    Args:
        path: 路径字符串
        max_depth: 最大深度
        
    Returns:
        是否通过验证
    """
    normalized = path.replace('\\', '/')
    parts = [p for p in normalized.split('/') if p and p not in ('.', '..')]
    return len(parts) <= max_depth


def sanitize_filename_strict(filename: str, max_length: int = MAX_FILENAME_LENGTH) -> str:
    """
    严格清理文件名（增强版）
    
    Args:
        filename: 原始文件名
        max_length: 最大长度
        
    Returns:
        清理后的文件名
    """
    if not isinstance(filename, str):
        return "unnamed"
    
    if not filename:
        return "unnamed"
    
    # 限制长度
    filename = filename[:max_length * 2]  # 先初步限制
    
    # 移除控制字符
    filename = ''.join(c for c in filename if ord(c) >= 32 and ord(c) != 127)
    
    # 替换非法字符
    filename = ILLEGAL_PATH_CHARS.sub('_', filename)
    
    # 替换路径分隔符
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # 移除首尾空格和点
    filename = filename.strip('. ')
    
    # 检查保留名称
    base_name = filename.split('.')[0].upper()
    if base_name in WINDOWS_RESERVED_NAMES:
        filename = f"_{filename}"
    
    # 最终长度限制
    if len(filename) > max_length:
        name, ext = os.path.splitext(filename)
        max_name_length = max_length - len(ext)
        if max_name_length < 1:
            filename = filename[:max_length]
        else:
            filename = name[:max_name_length] + ext
    
    return filename or "unnamed"


def is_safe_path(path: str, base_path: Optional[str] = None) -> bool:
    """
    检查路径是否安全（在基础路径范围内）
    
    Args:
        path: 要检查的路径
        base_path: 基础路径（如果提供，path必须是base_path的子路径）
        
    Returns:
        是否安全
    """
    try:
        # 解析路径
        path_obj = Path(path).resolve()
        
        if base_path:
            base_obj = Path(base_path).resolve()
            # 检查path是否在base_path之下
            try:
                path_obj.relative_to(base_obj)
                return True
            except ValueError:
                return False
        
        return True
    except Exception:
        return False


# ============ URL安全增强 ============

class URLValidationError(QBMonitorError):
    """URL验证错误"""
    pass


# 允许的URL协议
ALLOWED_URL_SCHEMES: Set[str] = {'http', 'https'}

# 危险的URL模式
DANGEROUS_URL_PATTERNS = [
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'data:', re.IGNORECASE),
    re.compile(r'vbscript:', re.IGNORECASE),
    re.compile(r'file:', re.IGNORECASE),
    re.compile(r'ftp:', re.IGNORECASE),
]

# IP地址相关模式（用于检测可能的SSRF）
PRIVATE_IP_PATTERNS = [
    re.compile(r'^(?:127\.)', re.IGNORECASE),                    # 127.0.0.0/8
    re.compile(r'^(?:10\.)', re.IGNORECASE),                     # 10.0.0.0/8
    re.compile(r'^(?:172\.(?:1[6-9]|2[0-9]|3[01])\.)', re.IGNORECASE),  # 172.16.0.0/12
    re.compile(r'^(?:192\.168\.)', re.IGNORECASE),               # 192.168.0.0/16
    re.compile(r'^(?:169\.254\.)', re.IGNORECASE),               # 169.254.0.0/16 (链路本地)
    re.compile(r'^(?:0\.)', re.IGNORECASE),                       # 0.0.0.0/8
]

# URL长度限制
MAX_URL_LENGTH = 2048
MAX_URL_PATH_LENGTH = 1024
MAX_URL_QUERY_LENGTH = 1024


def validate_url_strict(
    url: str,
    name: str = "URL",
    allow_private_ips: bool = True,
    require_https: bool = False
) -> None:
    """
    严格验证URL的安全性（增强版）
    
    Args:
        url: URL字符串
        name: 配置项名称（用于错误信息）
        allow_private_ips: 是否允许私有IP地址
        require_https: 是否强制HTTPS
        
    Raises:
        URLValidationError: 当URL不安全时
    """
    if not isinstance(url, str):
        raise URLValidationError(f"{name} 必须是字符串类型")
    
    if not url:
        raise URLValidationError(f"{name} 不能为空")
    
    url = url.strip()
    
    # 长度检查
    if len(url) > MAX_URL_LENGTH:
        raise URLValidationError(
            f"{name} 过长（最大{MAX_URL_LENGTH}字符）"
        )
    
    # 检查危险协议
    for pattern in DANGEROUS_URL_PATTERNS:
        if pattern.match(url):
            raise URLValidationError(
                f"{name} 使用了危险的协议"
            )
    
    # 解析URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise URLValidationError(f"{name} 解析失败: {e}")
    
    # 检查协议
    if not parsed.scheme:
        raise URLValidationError(f"{name} 缺少协议（如 http/https）")
    
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_URL_SCHEMES:
        raise URLValidationError(
            f"{name} 使用不支持的协议 '{parsed.scheme}'"
        )
    
    # HTTPS强制
    if require_https and scheme != 'https':
        raise URLValidationError(
            f"{name} 必须使用HTTPS协议"
        )
    
    # 检查主机
    if not parsed.netloc:
        raise URLValidationError(f"{name} 缺少主机地址")
    
    # 检查用户信息（防止凭证泄露）
    if parsed.username or parsed.password:
        raise URLValidationError(
            f"{name} 不应在URL中包含认证信息"
        )
    
    # 检查非法字符
    if CONTROL_CHARS.search(url):
        raise URLValidationError(f"{name} 包含非法控制字符")
    
    # 路径和查询长度检查
    if len(parsed.path) > MAX_URL_PATH_LENGTH:
        raise URLValidationError(
            f"{name} 路径过长（最大{MAX_URL_PATH_LENGTH}字符）"
        )
    
    if len(parsed.query) > MAX_URL_QUERY_LENGTH:
        raise URLValidationError(
            f"{name} 查询参数过长（最大{MAX_URL_QUERY_LENGTH}字符）"
        )
    
    # 检查私有IP（SSRF防护）
    if not allow_private_ips:
        hostname = parsed.hostname
        if hostname:
            for pattern in PRIVATE_IP_PATTERNS:
                if pattern.match(hostname):
                    raise URLValidationError(
                        f"{name} 指向私有IP地址，存在SSRF风险"
                    )


def sanitize_url(url: str) -> str:
    """
    清理URL
    
    Args:
        url: 原始URL
        
    Returns:
        清理后的URL
    """
    if not isinstance(url, str):
        return ""
    
    # 限制长度
    url = url[:MAX_URL_LENGTH]
    
    # 移除控制字符
    url = ''.join(c for c in url if ord(c) >= 32 and ord(c) != 127)
    
    # 移除HTML标签
    url = re.sub(r'<[^>]+>', '', url)
    
    return url.strip()


# ============ 主机名验证增强 ============

# 主机名最大长度
MAX_HOSTNAME_LENGTH = 253

# 危险字符模式（命令注入防护）
DANGEROUS_HOSTNAME_CHARS = re.compile(r'[;|&`$(){}\[\]<>]')

# 有效的主机名字符
VALID_HOSTNAME_CHARS = re.compile(r'^[a-zA-Z0-9.-]+$', re.ASCII)


def validate_hostname_strict(hostname: str, name: str = "hostname") -> None:
    """
    严格验证主机名的安全性（增强版）
    
    Args:
        hostname: 主机名字符串
        name: 配置项名称（用于错误信息）
        
    Raises:
        ConfigError: 当主机名不安全时
    """
    if not isinstance(hostname, str):
        raise ConfigError(f"{name} 必须是字符串类型")
    
    if not hostname:
        raise ConfigError(f"{name} 不能为空")
    
    hostname = hostname.strip()
    
    # 长度检查
    if len(hostname) > MAX_HOSTNAME_LENGTH:
        raise ConfigError(f"{name} 过长（最大{MAX_HOSTNAME_LENGTH}字符）")
    
    # 检查控制字符
    if CONTROL_CHARS.search(hostname):
        raise ConfigError(f"{name} 包含非法控制字符")
    
    # 检查危险字符（命令注入防护）
    if DANGEROUS_HOSTNAME_CHARS.search(hostname):
        raise ConfigError(
            f"{name} 包含危险字符，可能存在命令注入风险"
        )
    
    # 检查有效字符
    if not VALID_HOSTNAME_CHARS.match(hostname):
        # 允许IPv4地址
        if re.match(r'^(\d{1,3}\.){3}\d{1,3}$', hostname):
            return
        raise ConfigError(f"{name} 包含非法字符")


# ============ 内容大小限制 ============

@dataclass
class ContentLimits:
    """内容大小限制配置"""
    max_clipboard_size: int = 10 * 1024 * 1024  # 10MB
    max_magnet_count: int = 100                 # 单次处理最大磁力链接数
    max_text_line_length: int = 10000           # 单行最大长度
    max_text_lines: int = 10000                 # 最大行数


def validate_content_size(
    content: str,
    limits: Optional[ContentLimits] = None
) -> Tuple[bool, Optional[str]]:
    """
    验证内容大小是否在限制内
    
    Args:
        content: 内容字符串
        limits: 限制配置
        
    Returns:
        Tuple[bool, Optional[str]]: (是否有效, 错误信息)
    """
    if not isinstance(content, str):
        return False, "内容必须是字符串类型"
    
    limits = limits or ContentLimits()
    
    # 总大小检查
    content_bytes = content.encode('utf-8')
    if len(content_bytes) > limits.max_clipboard_size:
        return False, (
            f"内容过大（{len(content_bytes)} 字节），"
            f"最大允许 {limits.max_clipboard_size} 字节"
        )
    
    # 行数检查
    lines = content.split('\n')
    if len(lines) > limits.max_text_lines:
        return False, (
            f"内容行数过多（{len(lines)} 行），"
            f"最大允许 {limits.max_text_lines} 行"
        )
    
    # 单行长度检查
    for i, line in enumerate(lines[:100]):  # 只检查前100行
        if len(line) > limits.max_text_line_length:
            return False, (
                f"第 {i+1} 行过长（{len(line)} 字符），"
                f"最大允许 {limits.max_text_line_length} 字符"
            )
    
    return True, None


# ============ 特殊字符过滤 ============

# Unicode危险字符（双向字符等）
DANGEROUS_UNICODE_CHARS = re.compile(
    '['
    '\u202A-\u202E'  # 双向文本覆盖字符
    '\u2066-\u2069'  # 双向隔离字符
    ']'
)

# 常见的注入尝试模式
INJECTION_PATTERNS = [
    re.compile(r'<script', re.IGNORECASE),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),  # onclick=, onerror=等
    re.compile(r'eval\s*\(', re.IGNORECASE),
    re.compile(r'expression\s*\(', re.IGNORECASE),
]


def filter_special_chars(content: str) -> str:
    """
    过滤特殊字符（防止XSS和注入攻击）
    
    Args:
        content: 原始内容
        
    Returns:
        过滤后的内容
    """
    if not isinstance(content, str):
        return ""
    
    # 移除危险的Unicode字符
    content = DANGEROUS_UNICODE_CHARS.sub('', content)
    
    # HTML实体编码常见危险字符
    content = content.replace('&', '&amp;')
    content = content.replace('<', '&lt;')
    content = content.replace('>', '&gt;')
    content = content.replace('"', '&quot;')
    
    return content


def contains_injection_attempt(content: str) -> Tuple[bool, Optional[str]]:
    """
    检测内容是否包含注入尝试
    
    Args:
        content: 要检查的内容
        
    Returns:
        Tuple[bool, Optional[str]]: (是否包含注入, 检测到的模式)
    """
    if not isinstance(content, str):
        return False, None
    
    for pattern in INJECTION_PATTERNS:
        if pattern.search(content):
            return True, pattern.pattern
    
    return False, None


# ============ 安全头部生成 ============

def get_secure_headers_enhanced() -> Dict[str, str]:
    """
    获取增强的安全HTTP请求头部
    
    Returns:
        安全头部字典
    """
    return {
        'User-Agent': 'qbittorrent-clipboard-monitor/3.0.0',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        # 安全头部
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
    }


# ============ 安全常量（增强） ============

SAFE_TIMEOUTS = {
    'connect': 10,      # 连接超时
    'read': 30,         # 读取超时
    'total': 60,        # 总超时
    'ai_request': 30,   # AI请求超时
    'qb_request': 30,   # qBittorrent请求超时
}

SAFE_LIMITS = {
    'max_magnet_length': MAX_MAGNET_LENGTH,
    'max_path_length': MAX_PATH_LENGTH,
    'max_path_depth': MAX_PATH_DEPTH,
    'max_filename_length': MAX_FILENAME_LENGTH,
    'max_hostname_length': MAX_HOSTNAME_LENGTH,
    'max_retries': 10,
    'min_retry_delay': 0.5,
    'max_retry_delay': 60,
    'max_clipboard_size': 10 * 1024 * 1024,  # 10MB
    'max_magnets_per_check': 100,
}


# ============ 内存敏感数据清理 ============

def secure_clear_string(s: str) -> None:
    """
    尝试安全清除字符串内容
    
    注意：在CPython中，字符串是不可变的，此方法只能减少敏感数据
    在内存中的存活时间，无法完全清除。
    
    Args:
        s: 要清除的字符串
    """
    # Python字符串不可变，这里仅作为标记
    # 实际应用中应使用bytearray处理敏感数据
    del s


def secure_clear_dict(d: Dict[str, Any]) -> None:
    """
    清除字典中的敏感数据
    
    Args:
        d: 包含敏感数据的字典
    """
    sensitive_keys = {'password', 'api_key', 'apikey', 'secret', 'token', 'auth'}
    
    for key in list(d.keys()):
        if any(sk in key.lower() for sk in sensitive_keys):
            d[key] = '*' * len(str(d[key])) if d[key] else ''


# ============ 请求签名验证（用于Webhook等） ============

def generate_request_signature(
    payload: bytes,
    secret: str,
    algorithm: str = 'sha256'
) -> str:
    """
    生成请求签名
    
    Args:
        payload: 请求体内容
        secret: 签名密钥
        algorithm: 哈希算法（sha256或sha512）
        
    Returns:
        签名字符串
    """
    import hmac
    
    if algorithm not in ('sha256', 'sha512'):
        raise ValueError(f"不支持的算法: {algorithm}")
    
    hash_func = hashlib.sha256 if algorithm == 'sha256' else hashlib.sha512
    signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hash_func
    ).hexdigest()
    
    return f"{algorithm}={signature}"


def verify_request_signature(
    payload: bytes,
    signature_header: str,
    secret: str
) -> bool:
    """
    验证请求签名
    
    Args:
        payload: 请求体内容
        signature_header: 请求头中的签名（格式: algorithm=signature）
        secret: 签名密钥
        
    Returns:
        签名是否有效
    """
    try:
        expected = generate_request_signature(payload, secret)
        
        # 使用constant-time比较防止时序攻击
        return secrets.compare_digest(signature_header, expected)
    except Exception:
        return False


# ============ 安全审计日志 ============

def log_security_event(
    event_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    记录安全审计事件
    
    Args:
        event_type: 事件类型（validation_failed, rate_limited, injection_detected等）
        message: 事件描述
        details: 详细信息
    """
    import logging
    
    logger = logging.getLogger('security_audit')
    
    event_data = {
        'type': event_type,
        'message': message,
        'timestamp': time.time(),
        'details': details or {}
    }
    
    logger.warning(f"[SECURITY] {event_type}: {message}")


# ============ 向后兼容 ============

# 保持与旧代码的兼容性
validate_magnet = validate_magnet_strict
sanitize_magnet = sanitize_magnet_strict
extract_magnet_hash_safe = extract_magnet_hash_strict
validate_save_path = validate_save_path_strict
validate_url = validate_url_strict
validate_hostname = validate_hostname_strict
get_secure_headers = get_secure_headers_enhanced
