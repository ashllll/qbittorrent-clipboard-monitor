"""分类器模块测试"""

import pytest

from qbittorrent_monitor.classifier import ContentClassifier
from qbittorrent_monitor.config import Config, CategoryConfig


class TestRuleClassification:
    """规则分类测试"""
    
    @pytest.fixture
    def classifier(self, config):
        """创建分类器"""
        return ContentClassifier(config)
    
    def test_classify_movie(self, classifier):
        """测试电影分类"""
        result = classifier._rule_classify("The.Matrix.1999.1080p.BluRay.x264")
        assert result == "movies"
    
    def test_classify_tv(self, classifier):
        """测试电视剧分类"""
        result = classifier._rule_classify("Breaking.Bad.S01E01.720p")
        assert result == "tv"
    
    def test_classify_anime(self, classifier):
        """测试动画分类"""
        result = classifier._rule_classify("[GM-Team] Attack on Titan")
        assert result == "anime"
    
    def test_classify_other(self, classifier):
        """测试无法分类的情况"""
        result = classifier._rule_classify("Some.Random.File.v1.0")
        assert result is None
    
    def test_classify_empty(self, classifier):
        """测试空名称"""
        result = classifier.classify("")
        assert result == "other"
    
    def test_classify_none(self, classifier):
        """测试None名称"""
        result = classifier.classify(None)
        assert result == "other"


class TestCategoryConfig:
    """分类配置测试"""
    
    def test_category_keywords(self):
        """测试分类关键词"""
        cat = CategoryConfig(
            save_path="/downloads/test",
            keywords=["test", "example"],
        )
        assert cat.save_path == "/downloads/test"
        assert "test" in cat.keywords
