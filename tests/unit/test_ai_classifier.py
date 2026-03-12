"""AI 分类器单元测试

测试内容分类器的规则分类、AI 分类和缓存功能。
"""

from __future__ import annotations

import asyncio
import hashlib
import pytest
from typing import Dict, List, Optional
from unittest.mock import Mock, patch, AsyncMock

from qbittorrent_monitor.classifier import (
    ContentClassifier,
    ClassificationResult,
    LRUCache,
    AIClassifier,  # 兼容别名
)
from qbittorrent_monitor.config import Config, AIConfig, QBConfig, CategoryConfig


# ============================================================================
# TestLRUCache - LRU 缓存测试
# ============================================================================

class TestLRUCache:
    """LRU 缓存测试"""

    def test_cache_basic_operations(self) -> None:
        """测试缓存基本操作"""
        cache = LRUCache(capacity=10)
        
        result = ClassificationResult(category="movies", confidence=0.85, method="rule")
        cache.put("test_key", result)
        
        cached = cache.get("test_key")
        assert cached is not None
        assert cached.category == "movies"
        assert cached.cached is True

    def test_cache_miss(self) -> None:
        """测试缓存未命中"""
        cache = LRUCache(capacity=10)
        
        cached = cache.get("nonexistent")
        assert cached is None
        assert cache.misses == 1

    def test_cache_hit_counting(self) -> None:
        """测试缓存命中计数"""
        cache = LRUCache(capacity=10)
        
        result = ClassificationResult(category="tv", confidence=0.75, method="rule")
        cache.put("key", result)
        
        # 多次命中
        for _ in range(3):
            cache.get("key")
        
        assert cache.hits == 3

    def test_cache_eviction(self) -> None:
        """测试缓存淘汰"""
        cache = LRUCache(capacity=3)
        
        # 填满缓存
        for i in range(3):
            cache.put(f"key{i}", ClassificationResult(
                category=f"cat{i}",
                confidence=0.5,
                method="rule"
            ))
        
        # 访问 key0，使其成为最近使用
        cache.get("key0")
        
        # 添加新项，应该淘汰 key1
        cache.put("new", ClassificationResult(category="new", confidence=0.5, method="rule"))
        
        assert cache.get("key0") is not None
        assert cache.get("key1") is None
        assert cache.get("new") is not None

    def test_cache_clear(self) -> None:
        """测试清空缓存"""
        cache = LRUCache(capacity=10)
        
        for i in range(5):
            cache.put(f"key{i}", ClassificationResult(category="cat", confidence=0.5, method="rule"))
        
        cache.clear()
        
        assert len(cache.cache) == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_cache_stats(self) -> None:
        """测试缓存统计"""
        cache = LRUCache(capacity=10)
        
        # 一些命中和未命中
        cache.get("missing")  # miss
        cache.put("key", ClassificationResult(category="cat", confidence=0.5, method="rule"))
        cache.get("key")  # hit
        
        stats = cache.get_stats()
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5


# ============================================================================
# TestRuleBasedClassifier - 基于规则的分类器测试
# ============================================================================

class TestRuleBasedClassifier:
    """规则分类器测试"""

    @pytest.fixture
    def classifier(self, mock_config: Config) -> ContentClassifier:
        """分类器 fixture"""
        return ContentClassifier(mock_config, cache_size=100)

    def test_classify_movie(self, classifier: ContentClassifier) -> None:
        """测试电影分类"""
        result = classifier._rule_classify("The.Matrix.1999.1080p.BluRay.x264")
        
        assert result is not None
        assert result.category == "movies"
        assert result.method == "rule"
        assert result.confidence > 0.5

    def test_classify_tv(self, classifier: ContentClassifier) -> None:
        """测试电视剧分类"""
        result = classifier._rule_classify("Breaking.Bad.S01E01.1080p.WEB-DL")
        
        assert result is not None
        assert result.category == "tv"
        assert result.method == "rule"

    def test_classify_anime(self, classifier: ContentClassifier) -> None:
        """测试动画分类"""
        result = classifier._rule_classify("[GM-Team] Attack on Titan BD 1080p")
        
        assert result is not None
        assert result.category == "anime"
        assert result.method == "rule"

    def test_classify_music(self, classifier: ContentClassifier) -> None:
        """测试音乐分类"""
        result = classifier._rule_classify("Pink Floyd - The Wall FLAC 2024")
        
        assert result is not None
        assert result.category == "music"

    def test_classify_software(self, classifier: ContentClassifier) -> None:
        """测试软件分类"""
        result = classifier._rule_classify("Adobe Photoshop 2024 v25.0 Portable Software")
        
        assert result is not None
        assert result.category == "software"

    def test_classify_games(self, classifier: ContentClassifier) -> None:
        """测试游戏分类"""
        result = classifier._rule_classify("The Witcher 3 GOTY Edition CODEX")
        
        assert result is not None
        assert result.category == "games"

    def test_classify_books(self, classifier: ContentClassifier) -> None:
        """测试书籍分类"""
        result = classifier._rule_classify("Clean Code - Robert C. Martin PDF")
        
        assert result is not None
        assert result.category == "books"

    def test_classify_unknown(self, classifier: ContentClassifier) -> None:
        """测试未知内容"""
        result = classifier._rule_classify("xyz123 random content")
        
        # 应该返回 None，让后续处理降级
        assert result is None

    def test_classify_empty(self, classifier: ContentClassifier) -> None:
        """测试空内容"""
        result = classifier._rule_classify("")
        
        assert result is None

    def test_classify_case_insensitive(self, classifier: ContentClassifier) -> None:
        """测试不区分大小写"""
        result_lower = classifier._rule_classify("movie 1080p bluray")
        result_upper = classifier._rule_classify("MOVIE 1080P BLURAY")
        
        assert result_lower is not None
        assert result_upper is not None
        assert result_lower.category == result_upper.category

    def test_confidence_calculation(self, classifier: ContentClassifier) -> None:
        """测试置信度计算"""
        # 更多匹配应该带来更高置信度
        result1 = classifier._rule_classify("Movie 1080p")  # 一个匹配
        result2 = classifier._rule_classify("Movie 1080p BluRay 4K")  # 多个匹配
        
        assert result2.confidence > result1.confidence


# ============================================================================
# TestAIClassifier - AI 分类器测试
# ============================================================================

class TestAIClassifier:
    """AI 分类器测试"""

    @pytest.fixture
    def classifier(self, mock_config: Config) -> ContentClassifier:
        """分类器 fixture（AI 禁用）"""
        return ContentClassifier(mock_config, cache_size=100)

    @pytest.fixture
    def enabled_ai_config(self) -> Config:
        """启用 AI 的配置"""
        return Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(
                enabled=True,
                api_key="sk-test-key",
                model="deepseek-chat",
                base_url="https://api.deepseek.com/v1",
                timeout=30,
                max_retries=3
            ),
            categories={
                "movies": CategoryConfig(save_path="/downloads/movies"),
                "tv": CategoryConfig(save_path="/downloads/tv"),
                "anime": CategoryConfig(save_path="/downloads/anime"),
                "other": CategoryConfig(save_path="/downloads/other"),
            },
        )

    async def test_classify_with_disabled_ai(self, classifier: ContentClassifier) -> None:
        """测试 AI 禁用时使用规则分类"""
        result = await classifier.classify("The.Matrix.1999.1080p.BluRay")
        
        assert result.category == "movies"
        assert result.method == "rule"

    async def test_classify_empty_name(self, classifier: ContentClassifier) -> None:
        """测试空名称分类"""
        result = await classifier.classify("")
        
        assert result.category == "other"
        assert result.method == "fallback"
        assert result.confidence == 0.0

    async def test_classify_whitespace_only(self, classifier: ContentClassifier) -> None:
        """测试仅空白字符分类"""
        result = await classifier.classify("   \n\t  ")
        
        assert result.category == "other"
        assert result.method == "fallback"

    async def test_classify_caching(self, classifier: ContentClassifier) -> None:
        """测试分类结果缓存"""
        name = "Unique.Movie.Name.2024.1080p.BluRay"
        
        # 第一次分类
        result1 = await classifier.classify(name)
        
        # 第二次分类应该命中缓存
        result2 = await classifier.classify(name)
        
        assert result2.cached is True
        assert result1.category == result2.category

    async def test_classify_without_cache(self, classifier: ContentClassifier) -> None:
        """测试不使用缓存"""
        name = "Another.Unique.Name.2024"
        
        result = await classifier.classify(name, use_cache=False)
        
        assert result.cached is False

    async def test_cache_stats(self, classifier: ContentClassifier) -> None:
        """测试缓存统计"""
        # 一些分类操作
        await classifier.classify("Movie.2024.1080p.BluRay")
        await classifier.classify("Movie.2024.1080p.BluRay")  # 应该命中缓存
        await classifier.classify("TV.Show.S01E01.WEB-DL")
        
        stats = classifier.get_cache_stats()
        
        assert stats["size"] == 2
        assert stats["hits"] >= 1

    async def test_clear_cache(self, classifier: ContentClassifier) -> None:
        """测试清空缓存"""
        await classifier.classify("Test.Movie.2024.1080p")
        
        assert classifier.cache.get_stats()["size"] > 0
        
        classifier.clear_cache()
        
        assert classifier.cache.get_stats()["size"] == 0

    async def test_preload_cache(self, classifier: ContentClassifier) -> None:
        """测试预加载缓存"""
        names = ["Movie1", "Movie2", "Movie3"]
        categories = ["movies", "movies", "tv"]
        
        classifier.preload_cache(names, categories)
        
        stats = classifier.get_cache_stats()
        assert stats["size"] == 3

    async def test_classify_batch(self, classifier: ContentClassifier) -> None:
        """测试批量分类"""
        names = [
            "Movie.2024.1080p.BluRay",
            "TV.Show.S01E01.WEB-DL",
            "[GM-Team] Anime Series BD 1080p",
        ]
        
        results = await classifier.classify_batch(names)
        
        assert len(results) == 3
        assert results[0].category == "movies"
        assert results[1].category == "tv"
        assert results[2].category == "anime"

    async def test_classify_batch_empty(self, classifier: ContentClassifier) -> None:
        """测试空批量分类"""
        results = await classifier.classify_batch([])
        
        assert results == []

    async def test_classify_batch_with_exception(self, classifier: ContentClassifier) -> None:
        """测试批量分类异常处理"""
        # 创建一个会抛出异常的分类器方法
        original_classify = classifier.classify
        call_count = 0
        
        async def mock_classify(name, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValueError("Test error")
            return await original_classify(name, **kwargs)
        
        classifier.classify = mock_classify
        
        names = ["Movie.2024.1080p", "Problematic.Name", "TV.Show.S01E01"]
        results = await classifier.classify_batch(names, max_concurrent=1)
        
        # 应该返回结果，异常项返回 fallback
        assert len(results) == 3
        assert results[1].category == "other"
        assert results[1].confidence == 0.0


# ============================================================================
# TestAIClassificationWithMock - 带 Mock 的 AI 分类测试
# ============================================================================

class TestAIClassificationWithMock:
    """使用 Mock 的 AI 分类测试"""

    @pytest.fixture
    def ai_enabled_classifier(self) -> ContentClassifier:
        """AI 启用的分类器"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(
                enabled=True,
                api_key="sk-test-key-12345",
                model="deepseek-chat",
                base_url="https://api.deepseek.com/v1",
                timeout=30,
                max_retries=3
            ),
            categories={
                "movies": CategoryConfig(save_path="/downloads/movies"),
                "tv": CategoryConfig(save_path="/downloads/tv"),
                "anime": CategoryConfig(save_path="/downloads/anime"),
                "other": CategoryConfig(save_path="/downloads/other"),
            },
        )
        return ContentClassifier(config, cache_size=100)

    async def test_ai_classify_success(self, ai_enabled_classifier: ContentClassifier) -> None:
        """测试 AI 分类成功"""
        # Mock AI 客户端
        mock_response = Mock()
        mock_content = Mock()
        mock_content.text = "movies"
        mock_response.content = [mock_content]
        
        ai_enabled_classifier.client = Mock()
        ai_enabled_classifier.client.messages = Mock()
        ai_enabled_classifier.client.messages.create = Mock(return_value=mock_response)
        
        result = await ai_enabled_classifier._ai_classify_with_timeout("Test Movie Name")
        
        assert result is not None
        assert result.category == "movies"
        assert result.method == "ai"
        assert result.confidence == 0.85

    async def test_ai_classify_unrecognized_category(self, ai_enabled_classifier: ContentClassifier) -> None:
        """测试 AI 返回无法识别的分类"""
        mock_response = Mock()
        mock_content = Mock()
        mock_content.text = "unknown_category_xyz"
        mock_response.content = [mock_content]
        
        ai_enabled_classifier.client = Mock()
        ai_enabled_classifier.client.messages = Mock()
        ai_enabled_classifier.client.messages.create = Mock(return_value=mock_response)
        
        result = await ai_enabled_classifier._ai_classify_with_timeout("Test Name")
        
        assert result is not None
        assert result.category == "other"

    async def test_ai_classify_timeout(self, ai_enabled_classifier: ContentClassifier) -> None:
        """测试 AI 分类超时"""
        ai_enabled_classifier.client = Mock()
        ai_enabled_classifier.client.messages = Mock()
        ai_enabled_classifier.client.messages.create = Mock(
            side_effect=asyncio.TimeoutError()
        )
        
        with pytest.raises(asyncio.TimeoutError):
            await ai_enabled_classifier._ai_classify_with_timeout(
                "Test Name",
                timeout=0.01
            )

    async def test_ai_classify_exception(self, ai_enabled_classifier: ContentClassifier) -> None:
        """测试 AI 分类异常"""
        ai_enabled_classifier.client = Mock()
        ai_enabled_classifier.client.messages = Mock()
        ai_enabled_classifier.client.messages.create = Mock(
            side_effect=Exception("API Error")
        )
        
        with pytest.raises(Exception) as exc_info:
            await ai_enabled_classifier._ai_classify_with_timeout("Test Name")
        
        assert "API Error" in str(exc_info.value)

    async def test_ai_no_client(self, ai_enabled_classifier: ContentClassifier) -> None:
        """测试没有 AI 客户端时"""
        ai_enabled_classifier.client = None
        
        result = await ai_enabled_classifier._ai_classify_with_timeout("Test Name")
        
        assert result is None

    async def test_classify_fallback_to_rule(self, ai_enabled_classifier: ContentClassifier) -> None:
        """测试 AI 失败时降级到规则分类"""
        # 禁用客户端，触发降级
        ai_enabled_classifier.client = None
        
        result = await ai_enabled_classifier.classify("Movie.2024.1080p.BluRay")
        
        assert result.category == "movies"
        assert result.method == "rule"

    async def test_classify_high_confidence_rule(self, ai_enabled_classifier: ContentClassifier) -> None:
        """测试高置信度规则匹配跳过 AI"""
        # 即使启用了 AI，高置信度规则匹配也应该直接使用规则
        ai_enabled_classifier.client = Mock()  # 设置客户端
        ai_enabled_classifier.client.messages = Mock()
        ai_enabled_classifier.client.messages.create = Mock()
        
        result = await ai_enabled_classifier.classify("Movie.2024.1080p.BluRay.4K.WEB-DL")
        
        # 应该使用规则，没有调用 AI
        assert result.method == "rule"
        ai_enabled_classifier.client.messages.create.assert_not_called()

    async def test_classify_ai_confirms_rule(self, ai_enabled_classifier: ContentClassifier) -> None:
        """测试 AI 确认规则分类"""
        # Mock AI 返回与规则相同的分类
        mock_response = Mock()
        mock_content = Mock()
        mock_content.text = "movies"
        mock_response.content = [mock_content]
        
        ai_enabled_classifier.client = Mock()
        ai_enabled_classifier.client.messages = Mock()
        ai_enabled_classifier.client.messages.create = Mock(return_value=mock_response)
        
        # 使用低置信度规则匹配，触发 AI
        result = await ai_enabled_classifier.classify("Movie")  # 简单名称，低置信度
        
        # AI 确认后应该提高置信度
        assert result.category == "movies"
        assert result.confidence >= 0.9


# ============================================================================
# TestClassificationResult - 分类结果测试
# ============================================================================

class TestClassificationResult:
    """分类结果测试"""

    def test_result_creation(self) -> None:
        """测试结果创建"""
        result = ClassificationResult(
            category="movies",
            confidence=0.85,
            method="rule"
        )
        
        assert result.category == "movies"
        assert result.confidence == 0.85
        assert result.method == "rule"
        assert result.cached is False
        assert result.timestamp > 0

    def test_result_default_timestamp(self) -> None:
        """测试默认时间戳"""
        import time
        
        before = time.time()
        result = ClassificationResult(category="tv", confidence=0.75, method="ai")
        after = time.time()
        
        assert before <= result.timestamp <= after

    def test_result_equality(self) -> None:
        """测试结果相等性（逻辑上的）"""
        result1 = ClassificationResult(category="movies", confidence=0.85, method="rule")
        result2 = ClassificationResult(category="movies", confidence=0.85, method="rule")
        
        # 注意：由于 timestamp 可能不同，这里测试主要属性
        assert result1.category == result2.category
        assert result1.confidence == result2.confidence
        assert result1.method == result2.method


# ============================================================================
# TestKeywordBuilding - 关键词构建测试
# ============================================================================

class TestKeywordBuilding:
    """关键词构建测试"""

    def test_build_keywords_with_defaults(self, mock_config: Config) -> None:
        """测试构建关键词包含默认值"""
        classifier = ContentClassifier(mock_config)
        
        # 应该包含默认关键词
        assert "movies" in classifier._keywords
        assert "tv" in classifier._keywords
        assert len(classifier._keywords["movies"]) > 0

    def test_build_keywords_merge_config(self) -> None:
        """测试合并配置中的关键词"""
        config = Config(
            qbittorrent=QBConfig(
                host="localhost",
                port=8080,
                username="admin",
                password="adminadmin"
            ),
            ai=AIConfig(enabled=False),
            categories={
                "custom_cat": CategoryConfig(
                    save_path="/downloads/custom",
                    keywords=["custom_keyword1", "custom_keyword2"]
                ),
                "movies": CategoryConfig(
                    save_path="/downloads/movies",
                    keywords=["CustomMovieTag"]  # 额外关键词
                ),
            },
        )
        
        classifier = ContentClassifier(config)
        
        # 自定义分类应该有配置的关键词
        assert "custom_keyword1" in classifier._keywords["custom_cat"]
        assert "custom_keyword2" in classifier._keywords["custom_cat"]
        
        # movies 应该合并默认和自定义关键词
        assert "CustomMovieTag" in classifier._keywords["movies"]


# ============================================================================
# TestCacheKeyGeneration - 缓存键生成测试
# ============================================================================

class TestCacheKeyGeneration:
    """缓存键生成测试"""

    def test_cache_key_consistency(self, mock_config: Config) -> None:
        """测试缓存键一致性"""
        classifier = ContentClassifier(mock_config)
        
        key1 = classifier._get_cache_key("Test Movie Name")
        key2 = classifier._get_cache_key("Test Movie Name")
        
        assert key1 == key2

    def test_cache_key_case_insensitive(self, mock_config: Config) -> None:
        """测试缓存键不区分大小写"""
        classifier = ContentClassifier(mock_config)
        
        key1 = classifier._get_cache_key("TEST MOVIE NAME")
        key2 = classifier._get_cache_key("test movie name")
        key3 = classifier._get_cache_key("Test Movie Name")
        
        assert key1 == key2 == key3

    def test_cache_key_whitespace_trim(self, mock_config: Config) -> None:
        """测试缓存键去除空白"""
        classifier = ContentClassifier(mock_config)
        
        key1 = classifier._get_cache_key("  Test Movie Name  ")
        key2 = classifier._get_cache_key("Test Movie Name")
        
        assert key1 == key2

    def test_cache_key_format(self, mock_config: Config) -> None:
        """测试缓存键格式（MD5）"""
        classifier = ContentClassifier(mock_config)
        
        key = classifier._get_cache_key("test")
        
        # MD5 应该是 32 位十六进制字符串
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)


# ============================================================================
# TestConfidenceCalculation - 置信度计算测试
# ============================================================================

class TestConfidenceCalculation:
    """置信度计算测试"""

    def test_confidence_with_no_matches(self, mock_config: Config) -> None:
        """测试无匹配时的置信度"""
        classifier = ContentClassifier(mock_config)
        
        confidence = classifier._calculate_rule_confidence("name", "movies", 0)
        
        assert confidence == 0.0

    def test_confidence_with_matches(self, mock_config: Config) -> None:
        """测试有匹配时的置信度"""
        classifier = ContentClassifier(mock_config)
        
        confidence = classifier._calculate_rule_confidence("name", "movies", 1)
        
        # 基础置信度 0.5 + 匹配数量 0.1 = 0.6
        assert confidence >= 0.5

    def test_confidence_upper_bound(self, mock_config: Config) -> None:
        """测试置信度上限"""
        classifier = ContentClassifier(mock_config)
        
        # 很多匹配
        confidence = classifier._calculate_rule_confidence("name", "movies", 100)
        
        assert confidence <= 0.95

    def test_confidence_empty_keywords(self, mock_config: Config) -> None:
        """测试空关键词列表的置信度"""
        classifier = ContentClassifier(mock_config)
        
        confidence = classifier._calculate_rule_confidence("name", "nonexistent_category", 1)
        
        assert confidence == 0.5  # 默认置信度
