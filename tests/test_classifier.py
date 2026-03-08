"""分类器测试"""

import pytest
import asyncio

from qbittorrent_monitor.classifier import ContentClassifier, ClassificationResult, LRUCache
from qbittorrent_monitor.config import Config, CategoryConfig


def run_async(coro, event_loop):
    """辅助函数：运行异步协程"""
    return event_loop.run_until_complete(coro)


class TestContentClassifier:
    """测试内容分类器"""
    
    def test_rule_classify_movies(self, mock_config):
        """测试电影规则分类"""
        classifier = ContentClassifier(mock_config)
        
        result = classifier._rule_classify("Some Movie 1080p BluRay")
        assert result is not None
        assert result.category == "movies"
        assert result.method == "rule"
        assert result.confidence > 0
    
    def test_rule_classify_tv(self, mock_config):
        """测试电视剧规则分类"""
        classifier = ContentClassifier(mock_config)
        
        result = classifier._rule_classify("Show S01E01 HDTV")
        assert result is not None
        assert result.category == "tv"
        assert result.method == "rule"
    
    def test_rule_classify_no_match(self, mock_config):
        """测试无匹配情况"""
        classifier = ContentClassifier(mock_config)
        
        result = classifier._rule_classify("Unknown Content XYZ")
        assert result is None
    
    def test_classify_empty_name(self, mock_config, event_loop):
        """测试空名称"""
        classifier = ContentClassifier(mock_config)
        
        result = run_async(classifier.classify(""), event_loop)
        assert isinstance(result, ClassificationResult)
        assert result.category == "other"
        assert result.method == "fallback"
    
    def test_classify_with_rule_match(self, mock_config, event_loop):
        """测试异步分类（规则匹配）"""
        classifier = ContentClassifier(mock_config)
        
        result = run_async(classifier.classify("My Movie 1080p"), event_loop)
        assert isinstance(result, ClassificationResult)
        assert result.category == "movies"
        assert result.method == "rule"
    
    def test_classify_caching(self, mock_config, event_loop):
        """测试分类缓存功能"""
        classifier = ContentClassifier(mock_config)
        
        name = "Test Movie 4K HDR"
        
        # 第一次分类
        result1 = run_async(classifier.classify(name), event_loop)
        assert not result1.cached
        
        # 第二次分类（应该从缓存获取）
        result2 = run_async(classifier.classify(name), event_loop)
        assert result2.cached
        
        # 验证结果一致
        assert result1.category == result2.category
        
        # 验证缓存统计
        stats = classifier.get_cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
    
    def test_classify_no_cache(self, mock_config, event_loop):
        """测试禁用缓存"""
        classifier = ContentClassifier(mock_config)
        
        name = "Test Anime 1080p"
        
        # 不使用缓存
        result1 = run_async(classifier.classify(name, use_cache=False), event_loop)
        result2 = run_async(classifier.classify(name, use_cache=False), event_loop)
        
        assert not result1.cached
        assert not result2.cached
    
    def test_classify_batch(self, mock_config, event_loop):
        """测试批量分类"""
        classifier = ContentClassifier(mock_config)
        
        names = [
            "Movie 1 1080p BluRay",
            "TV Show S01E01",
            "Some Music FLAC",
            "Unknown XYZ Content"
        ]
        
        results = run_async(classifier.classify_batch(names), event_loop)
        
        assert len(results) == 4
        assert all(isinstance(r, ClassificationResult) for r in results)
        assert results[0].category == "movies"
        assert results[1].category == "tv"
        assert results[2].category == "music"
        assert results[3].category == "other"
    
    def test_classify_batch_empty(self, mock_config, event_loop):
        """测试批量分类空列表"""
        classifier = ContentClassifier(mock_config)
        
        results = run_async(classifier.classify_batch([]), event_loop)
        assert results == []
    
    def test_cache_clear(self, mock_config):
        """测试清空缓存"""
        classifier = ContentClassifier(mock_config)
        
        # 添加一些缓存
        result = ClassificationResult(category="movies", confidence=0.9, method="test")
        classifier.cache.put("test_key", result)
        
        assert classifier.cache.get_stats()["size"] == 1
        
        # 清空缓存
        classifier.clear_cache()
        assert classifier.cache.get_stats()["size"] == 0
    
    def test_preload_cache(self, mock_config):
        """测试预加载缓存"""
        classifier = ContentClassifier(mock_config)
        
        names = ["Movie A", "TV Show B", "Music C"]
        categories = ["movies", "tv", "music"]
        
        classifier.preload_cache(names, categories)
        
        stats = classifier.get_cache_stats()
        assert stats["size"] == 3
    
    def test_extended_keywords(self, mock_config):
        """测试扩展关键词库"""
        classifier = ContentClassifier(mock_config)
        
        # 测试新的关键词
        assert "4K" in classifier._keywords["movies"]
        assert "HDR" in classifier._keywords["movies"]
        assert "HEVC" in classifier._keywords["movies"]
        assert "x265" in classifier._keywords["movies"]
        assert "DTS" in classifier._keywords["movies"]
        assert "TrueHD" in classifier._keywords["movies"]
        
        # 测试 TV 关键词
        assert "S10" in classifier._keywords["tv"]
        assert "Season" in classifier._keywords["tv"]
        assert "Episode" in classifier._keywords["tv"]
        
        # 测试 Anime 关键词
        assert "BD" in classifier._keywords["anime"]
        assert "OVA" in classifier._keywords["anime"]
        
        # 测试 Music 关键词
        assert "FLAC" in classifier._keywords["music"]
        assert "320kbps" in classifier._keywords["music"]
        assert "Album" in classifier._keywords["music"]
        
        # 测试 Games 关键词（新增）
        assert "Steam" in classifier._keywords["games"]
        assert "CODEX" in classifier._keywords["games"]
        assert "REPACK" in classifier._keywords["games"]
        
        # 测试 Books 关键词（新增）
        assert "PDF" in classifier._keywords["books"]
        assert "EPUB" in classifier._keywords["books"]


class TestLRUCache:
    """测试 LRU 缓存"""
    
    def test_cache_basic_operations(self):
        """测试基本缓存操作"""
        cache = LRUCache(capacity=3)
        
        result = ClassificationResult(category="movies", confidence=0.9, method="test")
        
        # 添加
        cache.put("key1", result)
        assert cache.get("key1") is not None
        
        # 获取
        cached = cache.get("key1")
        assert cached.category == "movies"
        assert cached.cached is True
    
    def test_cache_eviction(self):
        """测试缓存淘汰"""
        cache = LRUCache(capacity=2)
        
        cache.put("key1", ClassificationResult("movies", 0.9, "test"))
        cache.put("key2", ClassificationResult("tv", 0.8, "test"))
        cache.put("key3", ClassificationResult("music", 0.7, "test"))
        
        # key1 应该被淘汰
        assert cache.get("key1") is None
        assert cache.get("key2") is not None
        assert cache.get("key3") is not None
    
    def test_cache_lru_order(self):
        """测试 LRU 顺序更新"""
        cache = LRUCache(capacity=3)
        
        cache.put("key1", ClassificationResult("a", 0.9, "test"))
        cache.put("key2", ClassificationResult("b", 0.8, "test"))
        cache.put("key3", ClassificationResult("c", 0.7, "test"))
        
        # 访问 key1，使其变为最近使用
        cache.get("key1")
        
        # 添加新项
        cache.put("key4", ClassificationResult("d", 0.6, "test"))
        
        # key2 应该被淘汰（最久未使用）
        assert cache.get("key2") is None
        assert cache.get("key1") is not None
        assert cache.get("key3") is not None
        assert cache.get("key4") is not None
    
    def test_cache_stats(self):
        """测试缓存统计"""
        cache = LRUCache(capacity=10)
        
        # 添加并获取
        cache.put("key1", ClassificationResult("movies", 0.9, "test"))
        cache.get("key1")  # hit
        cache.get("key1")  # hit
        cache.get("key2")  # miss
        
        stats = cache.get_stats()
        assert stats["size"] == 1
        assert stats["capacity"] == 10
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2/3


class TestClassificationResult:
    """测试分类结果类"""
    
    def test_result_creation(self):
        """测试结果创建"""
        result = ClassificationResult(
            category="movies",
            confidence=0.85,
            method="ai"
        )
        
        assert result.category == "movies"
        assert result.confidence == 0.85
        assert result.method == "ai"
        assert result.cached is False
        assert result.timestamp > 0
    
    def test_result_comparison(self):
        """测试结果比较"""
        result1 = ClassificationResult("movies", 0.9, "rule")
        result2 = ClassificationResult("movies", 0.9, "rule")
        result3 = ClassificationResult("tv", 0.8, "ai")
        
        assert result1.category == result2.category
        assert result1.category != result3.category
