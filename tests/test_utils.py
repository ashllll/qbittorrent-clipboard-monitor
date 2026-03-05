"""工具函数测试"""

import pytest

from qbittorrent_monitor.utils import parse_magnet, extract_magnet_hash


class TestParseMagnet:
    """磁力链接解析测试"""
    
    def test_parse_magnet_with_name(self):
        """测试解析带名称的磁力链接"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef\u0026dn=Test+Movie+2024"
        result = parse_magnet(magnet)
        assert result == "Test Movie 2024"
    
    def test_parse_magnet_without_name(self):
        """测试解析不带名称的磁力链接"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef"
        result = parse_magnet(magnet)
        assert result is None
    
    def test_parse_invalid_magnet(self):
        """测试解析无效的磁力链接"""
        result = parse_magnet("not-a-magnet")
        assert result is None
    
    def test_parse_empty(self):
        """测试解析空字符串"""
        result = parse_magnet("")
        assert result is None


class TestExtractHash:
    """磁力链接hash提取测试"""
    
    def test_extract_hash_lowercase(self):
        """测试提取小写hash"""
        magnet = "magnet:?xt=urn:btih:abc123def456"
        result = extract_magnet_hash(magnet)
        assert result == "abc123def456"
    
    def test_extract_hash_uppercase(self):
        """测试提取大写hash"""
        magnet = "magnet:?xt=urn:btih:ABC123DEF456"
        result = extract_magnet_hash(magnet)
        assert result == "abc123def456"
    
    def test_extract_hash_invalid(self):
        """测试提取无效链接的hash"""
        result = extract_magnet_hash("not-a-magnet")
        assert result is None
