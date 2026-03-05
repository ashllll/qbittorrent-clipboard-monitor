"""分类器测试"""

import pytest

from qbittorrent_monitor.classifier import ContentClassifier
from qbittorrent_monitor.config import Config, CategoryConfig


class TestContentClassifier:
    """内容分类器测试"""
    
    def test_rule_classify_movies(self, mock_config):
        """测试电影分类"""
        classifier = ContentClassifier(mock_config)
        
        result = classifier._rule_classify("The.Matrix.1999.1080p.BluRay")
        assert result == "movies"
        
        result = classifier._rule_classify("电影.复仇者联盟.4K")
        assert result == "movies"
    
    def test_rule_classify_tv(self, mock_config):
        """测试电视剧分类"""
        classifier = ContentClassifier(mock_config)
        
        result = classifier._rule_classify("Game.of.Thrones.S01E01")
        assert result == "tv"
        
        result = classifier._rule_classify("电视剧.狂飙.S01")
        assert result == "tv"
    
    def test_rule_classify_anime(self, mock_config):
        """测试动画分类"""
        classifier = ContentClassifier(mock_config)
        
        result = classifier._rule_classify("进击的巨人.Anime.1080p")
        assert result == "anime"
    
    def test_rule_classify_no_match(self, mock_config):
        """测试无匹配返回None"""
        classifier = ContentClassifier(mock_config)
        
        result = classifier._rule_classify("some.random.file.name")
        assert result is None
    
    def test_classify_empty_name(self, mock_config):
        """测试空名称返回other"""
        classifier = ContentClassifier(mock_config)
        
        result = classifier._rule_classify("")
        assert result is None
        
        # async method returns "other" for empty
        import asyncio
        result = asyncio.run(classifier.classify(""))
        assert result == "other"
    
    def test_classify_fallback_to_other(self, mock_config):
        """测试无匹配时返回other"""
        classifier = ContentClassifier(mock_config)
        
        import asyncio
        result = asyncio.run(classifier.classify("xyz.unknown.file"))
        assert result == "other"
