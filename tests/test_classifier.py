"""分类器测试"""

import pytest

from qbittorrent_monitor.classifier import ContentClassifier
from qbittorrent_monitor.config import Config, CategoryConfig


class TestContentClassifier:
    """测试内容分类器"""
    
    def test_rule_classify_movies(self, mock_config):
        """测试电影规则分类"""
        classifier = ContentClassifier(mock_config)
        
        result = classifier._rule_classify("Some Movie 1080p BluRay")
        assert result == "movies"
    
    def test_rule_classify_tv(self, mock_config):
        """测试电视剧规则分类"""
        classifier = ContentClassifier(mock_config)
        
        result = classifier._rule_classify("Show S01E01 1080p")
        assert result == "tv"
    
    def test_rule_classify_no_match(self, mock_config):
        """测试无匹配情况"""
        classifier = ContentClassifier(mock_config)
        
        result = classifier._rule_classify("Unknown Content XYZ")
        assert result is None
    
    def test_classify_empty_name(self, mock_config):
        """测试空名称"""
        classifier = ContentClassifier(mock_config)
        
        result = classifier.classify("")
        assert result == "other"
    
    @pytest.mark.asyncio
    async def test_classify_with_rule_match(self, mock_config):
        """测试异步分类（规则匹配）"""
        classifier = ContentClassifier(mock_config)
        
        result = await classifier.classify("My Movie 1080p")
        assert result == "movies"
