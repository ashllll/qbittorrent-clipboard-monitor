"""
安全工具模块

提供安全验证、输入清理、路径遍历防护等功能。
"""

import re
import os
from pathlib import Path
from typing import Optional, List, Tuple
from urllib.parse import urlparse

from .exceptions_unified import ConfigurationError


# ============ 磁力链接验证 ============

# 磁力链接正则模式
MAGNET_URI_PATTERN = re.compile(
    r'^magnet:\?xt=urn:btih:[a-f0-9]{40}',
    re.IGNORECASE
)

# 磁力链接hash提取模式
BTIH_PATTERN = re.compile(r'btih:([a-f0-9]{40})', re.IGNORECASE)

# 磁力链接最小长度
MIN_MAGNET_LENGTH = 50

# 磁力链接最大长度（防止DoS）
MAX_MAGNET_LENGTH = 8192


def validate_magnet(magnet: str) -> Tuple[bool, Optional[str]]:
    """
    验证磁力链接的有效性
    
    Args:
        magnet: 磁力链接字符串
        
    Returns:
        Tuple[bool, Optional[str]]: (是否有效, 错误信息)
    """
    if not magnet:
        return False, "磁力链接为空"
    
    if len(magnet) < MIN_MAGNET_LENGTH:
        return False, f"磁力链接过短（最小{MIN_MAGNET_LENGTH}字符）"
    
    if len(magnet) > MAX_MAGNET_LENGTH:
        return False, f"磁力链接过长（最大{MAX_MAGNET_LENGTH}字符）"
    
    # 验证必须以 magnet:? 开头
    if not magnet.startswith("magnet:?"):
        return False, "磁力链接格式错误：必须以magnet:?开头"
    
    # 验证 xt 参数存在且格式正确（40位十六进制或32位base32）
    if not MAGNET_URI_PATTERN.match(magnet):
        # 检查是否是32位base32编码的hash（旧格式）
        base32_pattern = re.compile(r'btih:([a-z2-7]{32})', re.IGNORECASE)
        if base32_pattern.search(magnet):
            # 继续执行后续验证
            pass
        else:
            return False, "磁力链接格式错误：缺少有效的btih hash"
    
    # 验证URL编码部分
    try:
        from urllib.parse import unquote
        decoded = unquote(magnet)
        # 检查是否包含控制字符
        if any(ord(c) < 32 for c in decoded):
            return False, "磁力链接包含非法字符"
    except Exception:
        return False, "磁力链接编码错误"
    
    # 安全增强：验证磁力链接只包含允许的字符
    allowed_pattern = re.compile(r'^[a-zA-Z0-9\-._~:/?#[\]@!$&\'()*+,;=]+$', re.ASCII)
    if not allowed_pattern.match(magnet):
        return False, "磁力链接包含非法字符"
    
    # 安全增强：验证参数键名安全
    param_pattern = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)=')
    for match in param_pattern.finditer(magnet):
        param_name = match.group(1)
        # 只允许标准磁力链接参数
        valid_params = {'xt', 'dn', 'tr', 'xl', 'as', 'xs', 'kt', 'mt', 'so'}
        if param_name not in valid_params:
            return False, f"不支持的参数: {param_name}"
    
    return True, None


def sanitize_magnet(magnet: str) -> str:
    """
    清理磁力链接，移除潜在危险字符
    
    Args:
        magnet: 原始磁力链接
        
    Returns:
        清理后的磁力链接
    """
    if not magnet:
        return ""
    
    # 限制长度
    magnet = magnet[:MAX_MAGNET_LENGTH]
    
    # 移除控制字符和空白字符
    magnet = ''.join(c for c in magnet if ord(c) >= 32 and c not in '\n\r\t')
    
    # 统一为小写的协议部分
    if magnet.lower().startswith('magnet:?'):
        magnet = 'magnet:?' + magnet[8:]
    
    return magnet


def extract_magnet_hash_safe(magnet: str) -> Optional[str]:
    """
    安全地提取磁力链接hash
    
    Args:
        magnet: 磁力链接
        
    Returns:
        hash字符串（40位十六进制小写），无效时返回None
    """
    is_valid, error = validate_magnet(magnet)
    if not is_valid:
        return None
    
    match = BTIH_PATTERN.search(magnet)
    if match:
        return match.group(1).lower()
    
    # 尝试匹配32位base32（转换为40位十六进制需要解码）
    base32_pattern = re.compile(r'btih:([a-z2-7]{32})', re.IGNORECASE)
    match = base32_pattern.search(magnet)
    if match:
        # 返回原始hash，不做base32解码
        return match.group(1).lower()
    
    return None


# ============ 路径遍历防护 ============

# 路径遍历危险模式
PATH_TRAVERSAL_PATTERNS = [
    re.compile(r'\.\.[\\/]'),  # ../ 或 ..\
    re.compile(r'[\\/]\.\.'),  # /.. 或 \..
    re.compile(r'\.\.\Z'),      # 以 .. 结尾
    re.compile(r'^\.\.'),       # 以 .. 开头
    re.compile(r'[~]'),          # 用户目录扩展
    re.compile(r'\$\w+'),        # 环境变量扩展
]

# 非法字符模式
ILLEGAL_PATH_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')

# 保留名称（Windows）
WINDOWS_RESERVED_NAMES = {
    'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
    'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4',
    'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
}


def validate_save_path(path: str, name: str = "save_path") -> None:
    """
    验证保存路径的安全性
    
    Args:
        path: 路径字符串
        name: 配置项名称（用于错误信息）
        
    Raises:
        ConfigurationError: 当路径存在安全风险时
    """
    if not path or not isinstance(path, str):
        raise ConfigurationError(f"{name} 不能为空")
    
    path = path.strip()
    
    if not path:
        raise ConfigurationError(f"{name} 不能为空字符串")
    
    # 检查路径遍历
    for pattern in PATH_TRAVERSAL_PATTERNS:
        if pattern.search(path):
            raise ConfigurationError(
                f"{name} 包含不安全的路径遍历序列: {path}"
            )
    
    # 检查非法字符
    if ILLEGAL_PATH_CHARS.search(path):
        raise ConfigurationError(
            f"{name} 包含非法字符: {path}"
        )
    
    # 检查Windows保留名称
    path_parts = path.replace('\\', '/').split('/')
    for part in path_parts:
        base_name = part.split('.')[0].upper()
        if base_name in WINDOWS_RESERVED_NAMES:
            raise ConfigurationError(
                f"{name} 包含Windows保留名称: {part}"
            )
    
    # 检查绝对路径是否合理
    if path.startswith('/') or (len(path) > 1 and path[1] == ':'):
        # 是绝对路径，检查是否在允许的根目录下
        # 可以在这里添加更多限制
        pass


def sanitize_filename(filename: str) -> str:
    """
    清理文件名，移除危险字符
    
    Args:
        filename: 原始文件名
        
    Returns:
        清理后的文件名
    """
    if not filename:
        return "unnamed"
    
    # 移除控制字符
    filename = ''.join(c for c in filename if ord(c) >= 32)
    
    # 替换非法字符
    filename = ILLEGAL_PATH_CHARS.sub('_', filename)
    
    # 移除路径分隔符
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # 移除首尾空格和点
    filename = filename.strip('. ')
    
    # 检查保留名称
    base_name = filename.split('.')[0].upper()
    if base_name in WINDOWS_RESERVED_NAMES:
        filename = f"_{filename}"
    
    # 限制长度
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    
    return filename or "unnamed"


# ============ URL 验证 ============

def validate_url(url: str, name: str = "URL") -> None:
    """
    验证URL的安全性
    
    Args:
        url: URL字符串
        name: 配置项名称（用于错误信息）
        
    Raises:
        ConfigurationError: 当URL不合法时
    """
    if not url or not isinstance(url, str):
        raise ConfigurationError(f"{name} 不能为空")
    
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ConfigurationError(f"{name} 解析失败: {e}")
    
    # 检查协议
    if not parsed.scheme:
        raise ConfigurationError(f"{name} 缺少协议（如 http/https）")
    
    allowed_schemes = {'http', 'https'}
    if parsed.scheme.lower() not in allowed_schemes:
        raise ConfigurationError(
            f"{name} 使用不支持的协议 '{parsed.scheme}'，"
            f"仅支持: {', '.join(allowed_schemes)}"
        )
    
    # 检查主机
    if not parsed.netloc:
        raise ConfigurationError(f"{name} 缺少主机地址")
    
    # 检查是否包含用户信息（用户:密码@主机）
    if parsed.username or parsed.password:
        raise ConfigurationError(
            f"{name} 不应在URL中包含认证信息"
        )
    
    # 检查非法字符
    if '\x00' in url or '\n' in url or '\r' in url:
        raise ConfigurationError(f"{name} 包含非法字符")


# ============ 主机名验证 ============

def validate_hostname(hostname: str, name: str = "hostname") -> None:
    """
    验证主机名的安全性
    
    Args:
        hostname: 主机名字符串
        name: 配置项名称（用于错误信息）
        
    Raises:
        ConfigurationError: 当主机名不合法时
    """
    if not hostname or not isinstance(hostname, str):
        raise ConfigurationError(f"{name} 不能为空")
    
    hostname = hostname.strip()
    
    # 检查长度
    if len(hostname) > 253:
        raise ConfigurationError(f"{name} 过长（最大253字符）")
    
    # 检查非法字符
    if '\x00' in hostname or '\n' in hostname or '\r' in hostname:
        raise ConfigurationError(f"{name} 包含非法字符")
    
    # 检查命令注入风险
    dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '{', '}', '<', '>']
    for char in dangerous_chars:
        if char in hostname:
            raise ConfigurationError(
                f"{name} 包含危险字符 '{char}'，可能存在命令注入风险"
            )


# ============ 敏感信息检测 ============

# 敏感字段名称模式
SENSITIVE_FIELD_PATTERNS = [
    re.compile(r'password', re.IGNORECASE),
    re.compile(r'passwd', re.IGNORECASE),
    re.compile(r'pwd', re.IGNORECASE),
    re.compile(r'secret', re.IGNORECASE),
    re.compile(r'token', re.IGNORECASE),
    re.compile(r'api[_-]?key', re.IGNORECASE),
    re.compile(r'api[_-]?secret', re.IGNORECASE),
    re.compile(r'private[_-]?key', re.IGNORECASE),
    re.compile(r'access[_-]?token', re.IGNORECASE),
    re.compile(r'refresh[_-]?token', re.IGNORECASE),
    re.compile(r'credential', re.IGNORECASE),
    re.compile(r'auth', re.IGNORECASE),
]


def is_sensitive_field(field_name: str) -> bool:
    """
    判断字段名是否为敏感字段
    
    Args:
        field_name: 字段名称
        
    Returns:
        是否为敏感字段
    """
    for pattern in SENSITIVE_FIELD_PATTERNS:
        if pattern.search(field_name):
            return True
    return False


def mask_sensitive_value(value: str, visible_chars: int = 3) -> str:
    """
    遮盖敏感值
    
    Args:
        value: 原始值
        visible_chars: 保留可见的前N个字符
        
    Returns:
        遮盖后的值
    """
    if not value:
        return "***"
    
    if len(value) <= visible_chars * 2:
        return "***"
    
    return value[:visible_chars] + "***" + value[-visible_chars:]


# ============ 安全头部生成 ============

def get_secure_headers() -> dict:
    """
    获取安全的HTTP请求头部
    
    Returns:
        安全头部字典
    """
    return {
        'User-Agent': 'qbittorrent-clipboard-monitor/3.0.0',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }


# ============ 安全常量 ============

# 安全的超时设置
SAFE_TIMEOUTS = {
    'connect': 10,      # 连接超时
    'read': 30,         # 读取超时
    'total': 60,        # 总超时
    'ai_request': 30,   # AI请求超时
    'qb_request': 30,   # qBittorrent请求超时
}

# 安全配置限制
SAFE_LIMITS = {
    'max_magnet_length': 8192,
    'max_path_length': 4096,
    'max_filename_length': 255,
    'max_hostname_length': 253,
    'max_retries': 10,
    'min_retry_delay': 0.5,
    'max_retry_delay': 60,
}
