"""工具函数模块"""

import re
from typing import Optional


def parse_magnet(magnet: str) -> Optional[str]:
    """解析磁力链接，返回显示名称"""
    if not magnet.startswith("magnet:?"):
        return None
    
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(magnet)
        params = urllib.parse.parse_qs(parsed.query)
        if "dn" in params:
            return params["dn"][0]
    except Exception:
        pass
    return None


def extract_magnet_hash(magnet: str) -> Optional[str]:
    """提取磁力链接的hash"""
    match = re.search(r'btih:([a-zA-Z0-9]+)', magnet, re.IGNORECASE)
    return match.group(1).lower() if match else None
