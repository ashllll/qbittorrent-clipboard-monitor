"""工具函数测试"""

import pytest

from qbittorrent_monitor.utils import parse_magnet, extract_magnet_hash


class TestParseMagnet:
    """测试磁力链接解析"""
    
    def test_valid_magnet_with_name(self):
        """测试有效的磁力链接（带名称）"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef\u0026dn=Test+Movie+2024"
        result = parse_magnet(magnet)
        assert result == "Test Movie 2024"
    
    def test_valid_magnet_without_name(self):
        """测试有效的磁力链接（无名称）"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef"
        result = parse_magnet(magnet)
        assert result is None
    
    def test_invalid_magnet(self):
        """测试无效的磁力链接"""
        result = parse_magnet("not a magnet link")
        assert result is None
    
    def test_empty_string(self):
        """测试空字符串"""
        result = parse_magnet("")
        assert result is None


class TestExtractMagnetHash:
    """测试磁力链接hash提取"""
    
    def test_extract_hash_lowercase(self):
        """测试小写hash"""
        magnet = "magnet:?xt=urn:btih:abc123def456"
        result = extract_magnet_hash(magnet)
        assert result == "abc123def456"
    
    def test_extract_hash_uppercase(self):
        """测试大写hash"""
        magnet = "magnet:?xt=urn:btih:ABC123DEF456"
        result = extract_magnet_hash(magnet)
        assert result == "abc123def456"
    
    def test_extract_hash_invalid(self):
        """测试无效的磁力链接"""
        result = extract_magnet_hash("not a magnet")
        assert result is None
