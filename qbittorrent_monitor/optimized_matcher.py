"""优化的关键词匹配引擎 - 使用 Aho-Corasick 算法"""
import time
from typing import Dict, List, Set, Tuple, Optional
from collections import deque

try:
    import ahocorasick
    AHOCORASICK_AVAILABLE = True
except ImportError:
    AHOCORASICK_AVAILABLE = False


class AhoCorasickMatcher:
    """Aho-Corasick 多模式匹配器
    
    时间复杂度: O(n + m + z)
    - n: 文本长度
    - m: 所有模式串总长度
    - z: 匹配结果数量
    
    比正则表达式快 10-50 倍
    """
    
    def __init__(self):
        self._automaton = ahocorasick.Automaton()
        self._category_map: Dict[str, str] = {}  # pattern -> category
        self._is_built = False
    
    def add_patterns(self, category: str, patterns: List[str]) -> None:
        """添加分类的关键词模式"""
        for pattern in patterns:
            # 转换为小写以实现大小写不敏感匹配
            pattern_lower = pattern.lower()
            key = f"{category}:{pattern_lower}"
            self._automaton.add_word(pattern_lower, key)
            self._category_map[key] = category
    
    def build(self) -> None:
        """构建自动机（必须在使用前调用）"""
        self._automaton.make_automaton()
        self._is_built = True
    
    def find_matches(self, text: str) -> Dict[str, List[str]]:
        """查找所有匹配
        
        Returns:
            {category: [matched_patterns]}
        """
        if not self._is_built:
            raise RuntimeError("Must call build() before matching")
        
        text_lower = text.lower()
        matches: Dict[str, List[str]] = {}
        
        for end_pos, key in self._automaton.iter(text_lower):
            category = self._category_map[key]
            pattern = key.split(':', 1)[1]
            
            if category not in matches:
                matches[category] = []
            if pattern not in matches[category]:
                matches[category].append(pattern)
        
        return matches
    
    def find_best_match(self, text: str) -> Optional[Tuple[str, int, float]]:
        """查找最佳匹配分类
        
        Returns:
            (category, match_count, confidence) 或 None
        """
        matches = self.find_matches(text)
        if not matches:
            return None
        
        # 选择匹配关键词最多的分类
        best_category = max(matches.items(), key=lambda x: len(x[1]))
        match_count = len(best_category[1])
        
        # 计算置信度
        confidence = min(0.5 + match_count * 0.1, 0.95)
        
        return (best_category[0], match_count, confidence)


class TrieMatcher:
    """简单 Trie 树匹配器（纯 Python，无需外部依赖）"""
    
    class TrieNode:
        __slots__ = ['children', 'is_end', 'category', 'pattern']
        
        def __init__(self):
            self.children: Dict[str, 'TrieMatcher.TrieNode'] = {}
            self.is_end = False
            self.category: Optional[str] = None
            self.pattern: Optional[str] = None
    
    def __init__(self):
        self._root = self.TrieNode()
        self._patterns_count = 0
    
    def add_pattern(self, pattern: str, category: str) -> None:
        """添加模式到 Trie"""
        node = self._root
        pattern_lower = pattern.lower()
        
        for char in pattern_lower:
            if char not in node.children:
                node.children[char] = self.TrieNode()
            node = node.children[char]
        
        node.is_end = True
        node.category = category
        node.pattern = pattern
        self._patterns_count += 1
    
    def find_matches(self, text: str) -> Dict[str, List[str]]:
        """在文本中查找所有匹配"""
        text_lower = text.lower()
        matches: Dict[str, List[str]] = {}
        
        for i in range(len(text_lower)):
            node = self._root
            matched_pattern = None
            matched_category = None
            
            for j in range(i, min(i + 100, len(text_lower))):  # 限制最大匹配长度
                char = text_lower[j]
                if char not in node.children:
                    break
                
                node = node.children[char]
                if node.is_end:
                    matched_pattern = node.pattern
                    matched_category = node.category
            
            if matched_pattern and matched_category:
                if matched_category not in matches:
                    matches[matched_category] = []
                if matched_pattern not in matches[matched_category]:
                    matches[matched_category].append(matched_pattern)
        
        return matches
    
    def find_best_match(self, text: str) -> Optional[Tuple[str, int, float]]:
        """查找最佳匹配分类"""
        matches = self.find_matches(text)
        if not matches:
            return None
        
        best_category = max(matches.items(), key=lambda x: len(x[1]))
        match_count = len(best_category[1])
        confidence = min(0.5 + match_count * 0.1, 0.95)
        
        return (best_category[0], match_count, confidence)


class OptimizedClassifier:
    """优化的内容分类器 - 使用高效匹配算法"""
    
    def __init__(self, keywords: Dict[str, List[str]]):
        """
        Args:
            keywords: 分类关键词字典 {category: [keywords]}
        """
        self._keywords = keywords
        self._matcher = self._build_matcher()
        
        # 统计
        self._rule_hits = 0
        self._fallback_hits = 0
    
    def _build_matcher(self):
        """构建匹配器"""
        if AHOCORASICK_AVAILABLE:
            try:
                matcher = AhoCorasickMatcher()
                for cat_name, words in self._keywords.items():
                    if cat_name != "other" and words:
                        matcher.add_patterns(cat_name, words)
                matcher.build()
                return matcher
            except Exception:
                pass
        
        # 回退到 Trie
        matcher = TrieMatcher()
        for cat_name, words in self._keywords.items():
            if cat_name != "other" and words:
                for word in words:
                    matcher.add_pattern(word, cat_name)
        return matcher
    
    def classify(self, name: str) -> Tuple[str, float, str]:
        """分类内容
        
        Returns:
            (category, confidence, method)
        """
        if not name or not name.strip():
            self._fallback_hits += 1
            return ("other", 0.3, "fallback")
        
        # 使用高效匹配
        result = self._matcher.find_best_match(name)
        
        if result:
            category, match_count, confidence = result
            self._rule_hits += 1
            return (category, confidence, "rule")
        
        self._fallback_hits += 1
        return ("other", 0.3, "fallback")
    
    def get_stats(self) -> Dict[str, int]:
        """获取分类统计"""
        total = self._rule_hits + self._fallback_hits
        return {
            "rule_hits": self._rule_hits,
            "fallback_hits": self._fallback_hits,
            "rule_rate": self._rule_hits / total if total > 0 else 0,
            "matcher_type": type(self._matcher).__name__,
        }
