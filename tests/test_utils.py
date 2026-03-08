"""工具函数测试 - 安全增强版"""

import pytest

from qbittorrent_monitor.utils import parse_magnet, extract_magnet_hash


class TestParseMagnet:
    """测试磁力链接解析"""
    
    def test_valid_magnet_with_name(self):
        """测试有效的磁力链接（带名称）"""
        # 使用有效的40位hash
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678&dn=Test+Movie+2024"
        result = parse_magnet(magnet)
        assert result == "Test Movie 2024"
    
    def test_valid_magnet_without_name(self):
        """测试有效的磁力链接（无名称）"""
        # 使用有效的40位hash
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
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
    
    def test_invalid_hash_length(self):
        """测试hash长度不足的磁力链接"""
        # 只有16位hash，应该是无效的
        magnet = "magnet:?xt=urn:btih:1234567890abcdef&dn=Test"
        result = parse_magnet(magnet)
        assert result is None  # 安全验证应该拒绝


class TestExtractMagnetHash:
    """测试磁力链接hash提取"""
    
    def test_extract_hash_lowercase(self):
        """测试小写hash - 需要有效的40位hash"""
        magnet = "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
        result = extract_magnet_hash(magnet)
        assert result == "1234567890abcdef1234567890abcdef12345678"
    
    def test_extract_hash_uppercase(self):
        """测试大写hash - 需要有效的40位hash"""
        magnet = "magnet:?xt=urn:btih:1234567890ABCDEF1234567890ABCDEF12345678"
        result = extract_magnet_hash(magnet)
        assert result == "1234567890abcdef1234567890abcdef12345678"
    
    def test_extract_hash_invalid(self):
        """测试无效的磁力链接"""
        result = extract_magnet_hash("not a magnet")
        assert result is None
    
    def test_extract_hash_too_short(self):
        """测试hash长度不足"""
        magnet = "magnet:?xt=urn:btih:abc123def456"
        result = extract_magnet_hash(magnet)
        # 安全验证应该拒绝hash长度不足的链接
        assert result is None
    
    def test_extract_hash_32char_base32(self):
        """测试32位base32格式的hash"""
        # 32位base32 hash（有效的替代格式）
        magnet = "magnet:?xt=urn:btih:abcdefghijklmnopqrstuvwx234567ab"
        result = extract_magnet_hash(magnet)
        assert result is not None
