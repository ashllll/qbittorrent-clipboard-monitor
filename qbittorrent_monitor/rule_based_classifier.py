"""规则引擎分类器

基于启发式规则的种子内容分类器，支持可配置的规则匹配和置信度计算。
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RuleBasedClassifier:
    """基于规则的分类器

    使用预定义的关键词规则和正则表达式对种子名称进行分类。
    支持置信度计算和多类别评分。

    Attributes:
        DEFAULT_HEURISTICS: 默认启发式规则字典

    Example:
        >>> classifier = RuleBasedClassifier()
        >>> categories = {"movies": ["电影", "Movie"], "tv": ["电视剧", "TV"]}
        >>> result = classifier.classify("Some Movie 1080p", categories)
        >>> print(result)  # "movies"
    """

    # 默认启发式规则
    DEFAULT_HEURISTICS: Dict[str, List[str]] = {
        "movies": [
            # 基础质量标识
            "1080p", "720p", "480p", "4K", "UHD", "HDR", "BluRay", "Blu-ray",
            "BDrip", "BRrip", "WEB-DL", "WEBRip", "WEB", "HDTV", "HDCAM",
            "CAM", "TS", "TC", "DVDrip", "DVDRip",
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
            r"S\d{1,2}", r"E\d{1,2}", "Season", "Episode",
            "Complete Season", "Season Complete",
            # 类型标识
            "电视剧", "Series", "TV Series", "TV Show", "Show",
            # 质量标识
            "1080p", "720p", "4K", "WEB-DL", "BluRay", "HDTV",
        ],
        "anime": [
            # 动画类型
            "动画", "Anime", "Animation",
            # 常见字幕组/发布组
            r"\[GM-Team\]", r"\[喵萌奶茶屋\]", r"\[诸神字幕组\]",
            r"\[桜都字幕组\]", r"\[极影字幕社\]", r"\[澄空学园\]",
            r"\[华盟字幕社\]", r"\[轻之国度\]", r"\[动漫国字幕组\]",
            r"\[漫猫字幕组\]", r"\[DHR字幕组\]",
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
            r"v\d+\.", "Portable", "Repack", "Preactivated", "Activated",
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
    }

    def __init__(self, heuristics: Optional[Dict[str, List[str]]] = None):
        """初始化规则分类器

        Args:
            heuristics: 自定义启发式规则，默认为 DEFAULT_HEURISTICS
        """
        self._heuristics = heuristics or self.DEFAULT_HEURISTICS
        self._compiled_patterns: Optional[Dict[str, re.Pattern]] = None

    def classify(
        self,
        torrent_name: str,
        categories: Optional[Dict[str, List[str]]] = None,
    ) -> Optional[str]:
        """对种子名称进行分类

        使用启发式规则和关键词匹配确定最适合的分类。

        Args:
            torrent_name: 种子名称
            categories: 可选的自定义分类规则，默认为初始化时的 heuristics

        Returns:
            分类名称，如果没有匹配则返回 None

        Example:
            >>> classifier = RuleBasedClassifier()
            >>> result = classifier.classify("My Movie 1080p BluRay")
            >>> print(result)  # "movies"
        """
        if not torrent_name or not torrent_name.strip():
            return None

        rules = categories or self._heuristics
        scores = self._calculate_scores(torrent_name.strip(), rules)

        if not scores:
            return None

        # 返回得分最高的分类
        best_category = max(scores.items(), key=lambda x: x[1])
        if best_category[1] > 0:
            return best_category[0]
        return None

    def classify_with_confidence(
        self,
        torrent_name: str,
        categories: Optional[Dict[str, List[str]]] = None,
    ) -> Optional[Tuple[str, float]]:
        """对种子名称进行分类并返回置信度

        Args:
            torrent_name: 种子名称
            categories: 可选的自定义分类规则

        Returns:
            (分类名称, 置信度) 元组，如果没有匹配则返回 None

        Example:
            >>> classifier = RuleBasedClassifier()
            >>> result = classifier.classify_with_confidence("Movie 1080p")
            >>> print(result)  # ("movies", 0.85)
        """
        if not torrent_name or not torrent_name.strip():
            return None

        rules = categories or self._heuristics
        scores = self._calculate_scores(torrent_name.strip(), rules)

        if not scores:
            return None

        # 返回得分最高的分类及其归一化置信度
        best_category, best_score = max(scores.items(), key=lambda x: x[1])
        if best_score > 0:
            # 计算置信度 (0.5 - 0.95 范围)
            confidence = min(0.5 + best_score * 0.1, 0.95)
            return (best_category, confidence)
        return None

    def _normalize_name(self, torrent_name: str) -> str:
        """规范化种子名称

        转换为小写并去除多余空白。

        Args:
            torrent_name: 原始种子名称

        Returns:
            规范化后的名称
        """
        return torrent_name.lower().strip()

    def _calculate_scores(
        self,
        torrent_name: str,
        rules: Dict[str, List[str]],
    ) -> Dict[str, int]:
        """计算各分类的匹配分数

        Args:
            torrent_name: 种子名称
            rules: 分类规则字典

        Returns:
            分类到分数的映射字典
        """
        normalized_name = self._normalize_name(torrent_name)
        scores: Dict[str, int] = {}

        for category, keywords in rules.items():
            if category == "other" or not keywords:
                continue

            score = self._apply_rule(normalized_name, keywords)
            if score > 0:
                scores[category] = score

        return scores

    def _apply_rule(self, normalized_name: str, keywords: List[str]) -> int:
        """应用规则计算匹配分数

        使用字符串匹配和正则表达式匹配关键词。

        Args:
            normalized_name: 规范化的种子名称
            keywords: 关键词列表

        Returns:
            匹配分数
        """
        score = 0
        matched_keywords = set()

        for keyword in keywords:
            if not keyword:
                continue

            # 检查是否是正则表达式（包含特殊字符）
            regex_special_chars = ".*+?^${}()|[]\\"
            is_regex = any(c in keyword for c in regex_special_chars)

            try:
                if is_regex:
                    pattern = re.compile(keyword, re.IGNORECASE)
                    matches = list(pattern.finditer(normalized_name))
                    if matches:
                        score += len(matches) * 2  # 正则匹配权重更高
                        matched_keywords.add(keyword)
                else:
                    # 简单的字符串匹配
                    keyword_lower = keyword.lower()
                    count = normalized_name.count(keyword_lower)
                    if count > 0:
                        # 长关键词权重更高
                        weight = max(1, len(keyword) // 3)
                        score += count * weight
                        matched_keywords.add(keyword)
            except re.error:
                # 正则表达式错误，降级为普通字符串匹配
                keyword_lower = keyword.lower()
                if keyword_lower in normalized_name:
                    score += 1
                    matched_keywords.add(keyword)

        return score

    def get_compiled_patterns(self) -> Dict[str, re.Pattern]:
        """获取预编译的正则表达式模式

        Returns:
            分类到编译后正则模式的映射
        """
        if self._compiled_patterns is None:
            self._compiled_patterns = self._build_keyword_patterns()
        return self._compiled_patterns

    def _build_keyword_patterns(self) -> Dict[str, re.Pattern]:
        """构建预编译的关键词正则模式

        将关键词列表编译为高效的正则表达式模式。

        Returns:
            分类到编译后正则模式的映射
        """
        patterns: Dict[str, re.Pattern] = {}

        for cat_name, keywords in self._heuristics.items():
            if cat_name == "other" or not keywords:
                continue

            # 按长度排序，优先匹配长关键词
            sorted_kws = sorted(
                (kw for kw in keywords if kw),
                key=len,
                reverse=True
            )

            if sorted_kws:
                # 转义并合并为正则
                escaped = [re.escape(kw) for kw in sorted_kws]
                pattern = re.compile("|".join(escaped), re.IGNORECASE)
                patterns[cat_name] = pattern

        return patterns

    def add_rule(self, category: str, keywords: List[str]) -> None:
        """添加自定义规则

        Args:
            category: 分类名称
            keywords: 关键词列表

        Example:
            >>> classifier = RuleBasedClassifier()
            >>> classifier.add_rule("custom", ["keyword1", "keyword2"])
        """
        if category not in self._heuristics:
            self._heuristics[category] = []

        self._heuristics[category].extend(keywords)
        # 清除缓存的模式，下次使用时重新编译
        self._compiled_patterns = None

    def remove_rule(self, category: str) -> bool:
        """移除规则

        Args:
            category: 要移除的分类名称

        Returns:
            是否成功移除
        """
        if category in self._heuristics:
            del self._heuristics[category]
            self._compiled_patterns = None
            return True
        return False

    def get_rules(self) -> Dict[str, List[str]]:
        """获取当前所有规则

        Returns:
            分类规则的副本
        """
        return dict(self._heuristics)
