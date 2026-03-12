"""内容分类器 - 增强版

支持规则分类、AI 分类、LRU 缓存、批量分类和置信度评估。
"""

import asyncio
import hashlib
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from functools import lru_cache

import anthropic

from .config import Config
from .exceptions_unified import AIError, AIFallbackError

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """分类结果"""
    category: str
    confidence: float  # 置信度 0.0-1.0
    method: str  # "rule", "ai", "fallback"
    cached: bool = False
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class LRUCache:
    """LRU 缓存实现"""
    
    def __init__(self, capacity: int = 1000):
        self.capacity = capacity
        self.cache: OrderedDict[str, ClassificationResult] = OrderedDict()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[ClassificationResult]:
        """获取缓存值"""
        if key not in self.cache:
            self.misses += 1
            return None
        # 移动到末尾（最近使用）
        self.cache.move_to_end(key)
        result = self.cache[key]
        result.cached = True
        self.hits += 1
        return result
    
    def put(self, key: str, value: ClassificationResult) -> None:
        """添加缓存值"""
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            # 移除最旧的项
            oldest = next(iter(self.cache))
            del self.cache[oldest]
    
    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0
        return {
            "size": len(self.cache),
            "capacity": self.capacity,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
        }


class ContentClassifier:
    """内容分类器 - 增强版
    
    特性：
    - 扩展的规则分类关键词库
    - LRU 缓存避免重复 AI 调用
    - 优雅的 AI 超时处理与降级
    - 批量分类支持
    - 分类置信度评估
    """
    
    # 扩展的默认关键词库
    DEFAULT_KEYWORDS: Dict[str, List[str]] = {
        "movies": [
            # 基础质量标识
            "1080p", "720p", "480p", "4K", "UHD", "HDR", "BluRay", "Blu-ray", "BDrip", "BRrip",
            "WEB-DL", "WEBRip", "WEB", "HDTV", "HDCAM", "CAM", "TS", "TC", "DVDrip", "DVDRip",
            # 编码格式
            "x264", "x265", "HEVC", "AVC", "H.264", "H.265", "10bit", "8bit",
            # 音频
            "DTS", "TrueHD", "Atmos", "DD5.1", "AAC", "AC3",
            # 类型标识
            "电影", "Movie", "Film", "Complete", "Director's Cut", "Extended",
            "Unrated", "Remastered", "Criterion", "IMAX",
        ],
        "tv": [
            # 季集标识
            "S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10",
            "S11", "S12", "S13", "S14", "S15", "S20", "S25", "S30",
            "E01", "E02", "E03", "E04", "E05", "E06", "E07", "E08", "E09", "E10",
            "E11", "E12", "E13", "E14", "E15", "E20", "E22", "E24",
            "Season", "Episode", "Complete Season", "Season Complete",
            # 类型标识
            "电视剧", "Series", "TV Series", "TV Show", "Show",
            # 质量标识
            "1080p", "720p", "4K", "WEB-DL", "BluRay", "HDTV",
        ],
        "anime": [
            # 动画类型
            "动画", "Anime", "Animation",
            # 常见字幕组/发布组
            "[GM-Team]", "[喵萌奶茶屋]", "[诸神字幕组]", "[桜都字幕组]",
            "[极影字幕社]", "[澄空学园]", "[华盟字幕社]", "[轻之国度]",
            "[动漫国字幕组]", "[漫猫字幕组]", "[DHR字幕组]",
            # 常见标识
            "BD", "TV版", "剧场版", "OVA", "OAD", "SP", "特典",
            "Season", "第", "季", "话", "集",
        ],
        "music": [
            # 音频格式
            "FLAC", "MP3", "MP4", "AAC", "ALAC", "WAV", "DSD", "SACD",
            "320kbps", "256kbps", "192kbps", "128kbps", "V0", "V2",
            # 类型标识
            "音乐", "Music", "Album", "EP", "Single", "Compilation",
            "OST", "Soundtrack", "Live", "Concert", "Remix", "Cover",
            # 发行相关
            "Discography", "Greatest Hits", "Best Of", "Anthology",
            "Deluxe Edition", "Limited Edition", "Bonus Tracks",
        ],
        "software": [
            # 软件类型
            "软件", "Software", "Program", "Application", "App",
            # 版本标识
            "v1.", "v2.", "v3.", "v4.", "v5.", "v6.", "v7.", "v8.", "v9.", "v10.",
            "Portable", "Repack", "Preactivated", "Activated",
            "Crack", "Keygen", "Patch", "License", "Serial",
            # 操作系统
            "Windows", "Linux", "macOS", "Mac", "Android", "iOS",
            # 开发相关
            "IDE", "Editor", "Tool", "Utility", "Driver", "Update",
        ],
        "games": [
            # 游戏平台
            "PC", "Steam", "GOG", "Epic",
            # 游戏类型
            "Game", "Games", "Gaming",
            # 常见标识
            "CODEX", "PLAZA", "HOODLUM", "FLT", "DARKSiDERS", "TiNYiSO",
            "SKIDROW", "RELOADED", "CPY", "FitGirl", "DODI",
            "Razor1911", "PROPHET", "HI2U", "ALiAS",
            # 版本标识
            "REPACK", "GOTY", "Deluxe", "Ultimate", "Complete",
            "Update", "DLC", "Expansion",
        ],
        "books": [
            # 格式
            "PDF", "EPUB", "MOBI", "AZW3", "AZW", "DJVU", "CBR", "CBZ",
            # 类型
            "Book", "Ebook", "电子书", "书籍", "小说", "Novel",
            # 出版相关
            "Publisher", "Edition", "Vol.", "Volume", "Chapter",
        ],
        "other": [],
    }
    
    def __init__(self, config: Config, cache_size: int = 1000):
        self.config = config
        self.ai_config = config.ai
        self.client: Optional[anthropic.Anthropic] = None
        
        # 初始化 AI 客户端 (Minimax Anthropic API 格式)
        if self.ai_config.enabled and self.ai_config.api_key:
            try:
                self.client = anthropic.Anthropic(
                    api_key=self.ai_config.api_key, 
                    base_url=self.ai_config.base_url
                )
                logger.debug("AI 客户端初始化成功 (Minimax Anthropic API)")
            except Exception as e:
                logger.warning(f"AI 客户端初始化失败: {e}")
                self.client = None
        
        # 初始化 LRU 缓存
        self.cache = LRUCache(capacity=cache_size)
        
        # 合并默认关键词和配置关键词
        self._keywords = self._build_keywords()
        
        # 批量分类的并发限制
        self._semaphore = asyncio.Semaphore(5)
    
    def _build_keywords(self) -> Dict[str, List[str]]:
        """构建合并后的关键词库"""
        keywords = dict(self.DEFAULT_KEYWORDS)
        
        # 合并配置中的关键词
        for cat_name, cat_config in self.config.categories.items():
            if cat_config.keywords:
                if cat_name in keywords:
                    # 合并并去重
                    existing = set(k.lower() for k in keywords[cat_name])
                    for kw in cat_config.keywords:
                        if kw.lower() not in existing:
                            keywords[cat_name].append(kw)
                else:
                    keywords[cat_name] = list(cat_config.keywords)
        
        return keywords
    
    def _build_keyword_patterns(self) -> Dict[str, re.Pattern]:
        """构建预编译的关键词正则模式 - 性能优化"""
        patterns = {}
        for cat_name, keywords in self._keywords.items():
            if cat_name == "other" or not keywords:
                continue
            
            # 按长度排序，优先匹配长关键词
            sorted_kws = sorted(keywords, key=len, reverse=True)
            # 转义并合并为正则
            pattern = re.compile(
                '|'.join(re.escape(kw) for kw in sorted_kws),
                re.IGNORECASE
            )
            patterns[cat_name] = pattern
        return patterns
    
    def _get_cache_key(self, name: str) -> str:
        """生成缓存键 - 使用 MD5 优化性能"""
        return hashlib.md5(name.lower().strip().encode()).hexdigest()
    
    def _calculate_rule_confidence(self, name: str, category: str, matched_count: int = 1) -> float:
        """计算规则分类的置信度 - 优化版"""
        keywords = self._keywords.get(category, [])
        
        if not keywords:
            return 0.5
        
        # 基于匹配数量和关键词长度计算置信度
        if matched_count == 0:
            return 0.0
        
        # 匹配的关键词越多，置信度越高
        base_confidence = min(0.5 + matched_count * 0.1, 0.8)
        
        # 根据匹配比例增加置信度
        match_ratio = matched_count / len(keywords)
        ratio_bonus = min(match_ratio * 0.2, 0.15)
        
        return min(base_confidence + ratio_bonus, 0.95)
    
    def _rule_classify(self, name: str) -> Optional[ClassificationResult]:
        """规则分类 - 性能优化版
        
        使用预编译正则表达式，时间复杂度从 O(n*m) 优化到 O(n)
        返回包含置信度的分类结果
        """
        if not name:
            return None
        
        name_lower = name.lower()
        best_match: Optional[Tuple[str, float]] = None
        
        # 使用预编译的正则模式进行快速匹配
        if not hasattr(self, '_keyword_patterns'):
            self._keyword_patterns = self._build_keyword_patterns()
        
        for cat_name, pattern in self._keyword_patterns.items():
            matches = list(pattern.finditer(name_lower))
            if matches:
                # 计算置信度
                confidence = self._calculate_rule_confidence(
                    name, cat_name, len(matches)
                )
                if best_match is None or confidence > best_match[1]:
                    best_match = (cat_name, confidence)
        
        if best_match:
            return ClassificationResult(
                category=best_match[0],
                confidence=best_match[1],
                method="rule"
            )
        
        return None
    
    async def _ai_classify_with_timeout(
        self, 
        name: str, 
        timeout: Optional[float] = None
    ) -> Optional[ClassificationResult]:
        """带超时的 AI 分类"""
        if not self.client:
            return None
        
        timeout = timeout or self.ai_config.timeout
        
        def _call():
            # Minimax Anthropic API 格式
            return self.client.messages.create(
                model=self.ai_config.model,
                system=(
                    "你是一个种子内容分类助手。请分析给定的种子名称，"
                    "从以下分类中选择最合适的一个：movies, tv, anime, music, "
                    "software, games, books, other。只返回分类名称，不要其他解释。"
                ),
                messages=[
                    {
                        "role": "user", 
                        "content": f"种子名称: {name}\n请返回分类:"
                    },
                ],
                temperature=0.3,
                max_tokens=20,
            )
        
        try:
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, _call), 
                timeout=timeout
            )
            # Anthropic API 响应格式: response.content[0].text
            result_text = response.content[0].text.strip().lower()
            
            # 验证结果并返回
            valid_categories = list(self._keywords.keys())
            for cat in valid_categories:
                if cat in result_text:
                    # AI 分类的基础置信度较高
                    return ClassificationResult(
                        category=cat,
                        confidence=0.85,
                        method="ai"
                    )
            
            # 如果 AI 返回了无法识别的分类，返回 other
            logger.warning(f"AI 返回了无法识别的分类: {result_text}")
            return ClassificationResult(
                category="other",
                confidence=0.5,
                method="ai"
            )
            
        except asyncio.TimeoutError:
            logger.warning(f"AI 分类超时 ({timeout}s): {name[:50]}...")
            raise
        except Exception as e:
            logger.warning(f"AI 分类失败: {e}")
            raise
    
    async def classify(
        self, 
        name: str, 
        use_cache: bool = True,
        timeout: Optional[float] = None
    ) -> ClassificationResult:
        """分类单个内容
        
        Args:
            name: 内容名称
            use_cache: 是否使用缓存
            timeout: AI 分类超时时间，默认使用配置值
            
        Returns:
            ClassificationResult: 包含分类、置信度、方法等信息的结果
        """
        if not name or not name.strip():
            return ClassificationResult(
                category="other",
                confidence=0.0,
                method="fallback"
            )
        
        name = name.strip()
        cache_key = self._get_cache_key(name)
        
        # 检查缓存
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"缓存命中: {name[:50]}... -> {cached.category}")
                return cached
        
        # 规则分类
        rule_result = self._rule_classify(name)
        if rule_result and rule_result.confidence >= 0.7:
            # 高置信度规则匹配，直接使用
            if use_cache:
                self.cache.put(cache_key, rule_result)
            logger.debug(f"规则分类: {name[:50]}... -> {rule_result.category} ({rule_result.confidence:.2f})")
            return rule_result
        
        # 尝试 AI 分类
        if self.client and self.ai_config.enabled:
            try:
                ai_result = await self._ai_classify_with_timeout(name, timeout)
                if ai_result:
                    # 如果之前有规则分类但置信度不高，结合两者
                    if rule_result and rule_result.category == ai_result.category:
                        # 分类一致，提高置信度
                        ai_result.confidence = min(ai_result.confidence + 0.1, 1.0)
                    
                    if use_cache:
                        self.cache.put(cache_key, ai_result)
                    logger.debug(f"AI 分类: {name[:50]}... -> {ai_result.category} ({ai_result.confidence:.2f})")
                    return ai_result
                    
            except asyncio.TimeoutError:
                # 超时降级到规则分类
                logger.info(f"AI 超时，降级到规则分类: {name[:50]}...")
            except Exception as e:
                logger.warning(f"AI 失败，降级到规则分类: {e}")
        
        # 使用规则分类结果（如果有）
        if rule_result:
            if use_cache:
                self.cache.put(cache_key, rule_result)
            return rule_result
        
        # 最终降级
        fallback_result = ClassificationResult(
            category="other",
            confidence=0.3,
            method="fallback"
        )
        if use_cache:
            self.cache.put(cache_key, fallback_result)
        
        return fallback_result
    
    async def classify_batch(
        self, 
        names: List[str], 
        use_cache: bool = True,
        timeout: Optional[float] = None,
        max_concurrent: int = 5
    ) -> List[ClassificationResult]:
        """批量分类内容
        
        Args:
            names: 内容名称列表
            use_cache: 是否使用缓存
            timeout: AI 分类超时时间
            max_concurrent: 最大并发数
            
        Returns:
            List[ClassificationResult]: 分类结果列表
        """
        if not names:
            return []
        
        # 创建信号量限制并发
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _classify_one(name: str) -> ClassificationResult:
            async with semaphore:
                return await self.classify(name, use_cache=use_cache, timeout=timeout)
        
        # 并发执行所有分类任务
        tasks = [_classify_one(name) for name in names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        final_results: List[ClassificationResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"分类失败 '{names[i][:50]}...': {result}")
                final_results.append(ClassificationResult(
                    category="other",
                    confidence=0.0,
                    method="fallback"
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return self.cache.get_stats()
    
    def clear_cache(self) -> None:
        """清空分类缓存"""
        self.cache.clear()
        logger.info("分类缓存已清空")
    
    def preload_cache(self, names: List[str], results: List[str]) -> None:
        """预加载缓存
        
        Args:
            names: 内容名称列表
            results: 对应分类结果列表
        """
        for name, category in zip(names, results):
            cache_key = self._get_cache_key(name)
            result = ClassificationResult(
                category=category,
                confidence=0.9,
                method="preloaded"
            )
            self.cache.put(cache_key, result)
        
        logger.info(f"预加载了 {len(names)} 条缓存")


# 兼容旧名
AIClassifier = ContentClassifier
