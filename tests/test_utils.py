"""工具函数测试"""

import pytest

from qbittorrent_monitor.utils import parse_magnet, extract_magnet_hash


class TestUtils:
    """工具函数测试"""
    
    def test_parse_magnet_with_dn(self):
        """测试解析带名称的磁力链接"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef\u0026dn=Test+File+Name"
        result = parse_magnet(magnet)
        assert result == "Test File Name"
    
    def test_parse_magnet_without_dn(self):
        """测试解析无名称的磁力链接"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef"
        result = parse_magnet(magnet)
        assert result is None
    
    def test_parse_magnet_invalid(self):
        """测试解析无效链接"""
        result = parse_magnet("not-a-magnet-link")
        assert result is None
        
        result = parse_magnet("")
        assert result is None
    
    def test_extract_hash(self):
        """测试提取hash"""
        magnet = "magnet:?xt=urn:btih:ABC123DEF456"
        result = extract_magnet_hash(magnet)
        assert result == "abc123def456"
    
    def test_extract_hash_lowercase(self):
        """测试提取小写hash"""
        magnet = "magnet:?xt=urn:btih:abc123"
        result = extract_magnet_hash(magnet)
        assert result == "abc123"
    
    def test_extract_hash_invalid(self):
        """测试提取无效hash"""
        result = extract_magnet_hash("not-a-magnet")
        assert result is None
