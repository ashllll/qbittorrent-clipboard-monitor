"""统一的磁力链接处理模块

蜂群优化：统一所有磁力链接相关操作，替代分散的函数。
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Optional, List, NamedTuple
from dataclasses import dataclass

from ..security import validate_magnet, sanitize_magnet


class MagnetInfo(NamedTuple):
    """磁力链接信息"""
    raw: str                    # 原始链接
    hash: str                  # info hash
    name: Optional[str]        # 显示名称 (dn)
    trackers: List[str]        # tracker列表


@dataclass(frozen=True)
class MagnetLimits:
    """磁力链接限制常量"""
    MIN_LENGTH: int = 50
    MAX_LENGTH: int = 8192
    MAX_CONTENT_MULTIPLIER: int = 10
    MAX_DISPLAY_LENGTH: int = 100


class MagnetProcessor:
    """磁力链接处理器 - 蜂群优化版
    
    统一所有磁力链接相关操作：
    - 提取和解析
    - 验证和清理
    - 显示名称生成
    
    替代原有的分散函数：
    - utils.extract_magnet_hash()
    - utils.parse_magnet()
    - utils.get_magnet_display_name()
    - security.extract_magnet_hash_safe()
    - monitor.MagnetExtractor
    """
    
    # 预编译正则
    MAGNET_PATTERN = re.compile(
        r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{32,40}',
        re.IGNORECASE
    )
    BTIH_PATTERN = re.compile(
        r'btih:([a-fA-F0-9]{40}|[a-z2-7]{32})',
        re.IGNORECASE
    )
    
    def __init__(self, limits: Optional[MagnetLimits] = None):
        self.limits = limits or MagnetLimits()
    
    def extract(self, content: str) -> List[str]:
        """从内容中提取所有磁力链接
        
        Args:
            content: 可能包含磁力链接的文本
            
        Returns:
            去重后的磁力链接列表
        """
        if not content or len(content) < self.limits.MIN_LENGTH:
            return []
        
        # 安全检查：限制处理内容大小
        max_content_len = self.limits.MAX_LENGTH * self.limits.MAX_CONTENT_MULTIPLIER
        if len(content) > max_content_len:
            content = content[:max_content_len]
        
        # 快速检查
        if 'magnet:?' not in content:
            return []
        
        matches = self.MAGNET_PATTERN.findall(content)
        seen: set[str] = set()
        results: List[str] = []
        
        for magnet in matches:
            magnet = sanitize_magnet(magnet)
            is_valid, _ = validate_magnet(magnet)
            if not is_valid:
                continue
            
            magnet_hash = self.get_hash(magnet)
            if magnet_hash and magnet_hash not in seen:
                seen.add(magnet_hash)
                results.append(magnet)
        
        return results
    
    def get_hash(self, magnet: str) -> Optional[str]:
        """提取磁力链接的hash
        
        Args:
            magnet: 磁力链接
            
        Returns:
            40位十六进制hash，无效时返回None
        """
        match = self.BTIH_PATTERN.search(magnet)
        if match:
            return match.group(1).lower()
        return None
    
    def get_name(self, magnet: str) -> Optional[str]:
        """提取显示名称 (dn参数)
        
        Args:
            magnet: 磁力链接
            
        Returns:
            种子名称，无效时返回None
        """
        try:
            parsed = urllib.parse.urlparse(magnet)
            params = urllib.parse.parse_qs(parsed.query)
            if "dn" in params:
                return params["dn"][0]
        except Exception:
            pass
        return None
    
    def parse(self, magnet: str) -> Optional[MagnetInfo]:
        """完整解析磁力链接
        
        Args:
            magnet: 磁力链接
            
        Returns:
            MagnetInfo对象，无效时返回None
        """
        is_valid, error = validate_magnet(magnet)
        if not is_valid:
            return None
        
        magnet_hash = self.get_hash(magnet)
        if not magnet_hash:
            return None
        
        return MagnetInfo(
            raw=magnet,
            hash=magnet_hash,
            name=self.get_name(magnet),
            trackers=self._get_trackers(magnet)
        )
    
    def _get_trackers(self, magnet: str) -> List[str]:
        """获取tracker列表"""
        try:
            parsed = urllib.parse.urlparse(magnet)
            params = urllib.parse.parse_qs(parsed.query)
            return params.get("tr", [])
        except Exception:
            return []
    
    def get_display_name(self, magnet: str, max_length: int = 100) -> str:
        """获取显示名称（用于日志）
        
        优先尝试解析种子名称（dn参数），如果没有则使用hash截断
        
        Args:
            magnet: 磁力链接
            max_length: 最大长度
            
        Returns:
            安全的显示字符串
        """
        # 首先尝试解析种子名称
        name = self.get_name(magnet)
        if name:
            if len(name) > max_length:
                return name[:max_length] + "..."
            return name
        
        # 没有名称时，使用 hash 截断
        magnet_hash = self.get_hash(magnet)
        if magnet_hash:
            return f"magnet:...{magnet_hash[-8:]}"
        
        # 回退到原始截断
        if len(magnet) > max_length:
            return magnet[:max_length] + "..."
        return magnet
    
    def is_valid(self, magnet: str) -> bool:
        """快速验证磁力链接有效性
        
        Args:
            magnet: 要检查的字符串
            
        Returns:
            是否为有效的磁力链接
        """
        is_valid, _ = validate_magnet(magnet)
        return is_valid
