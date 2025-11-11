"""
智能内容过滤模块

提供：
- 文件大小过滤
- 做种数过滤
- 关键词过滤
- 重复内容检测
- 质量评分系统
- 格式优先级
"""

import re
import logging
import hashlib
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from difflib import SequenceMatcher

from .enhanced_cache import get_global_cache
from .utils import parse_magnet, validate_magnet_link

logger = logging.getLogger(__name__)


class FilterAction(Enum):
    """过滤动作"""
    ALLOW = "allow"  # 允许
    BLOCK = "block"  # 阻止
    PRIORITY = "priority"  # 优先
    FLAG = "flag"  # 标记


class ContentQuality(Enum):
    """内容质量等级"""
    EXCELLENT = "excellent"  # 优秀
    GOOD = "good"  # 良好
    AVERAGE = "average"  # 一般
    POOR = "poor"  # 较差
    REJECT = "reject"  # 拒绝


@dataclass
class FilterRule:
    """过滤规则"""
    name: str
    action: FilterAction
    pattern: str
    pattern_type: str  # 'keyword', 'regex', 'size', 'seeders'
    priority: int = 0
    enabled: bool = True
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentInfo:
    """内容信息"""
    title: str
    magnet_link: str
    size: Optional[int] = None
    seeders: int = 0
    leechers: int = 0
    category: str = ""
    hash: Optional[str] = None
    quality_score: float = 0.0
    quality_level: ContentQuality = ContentQuality.AVERAGE
    tags: List[str] = field(default_factory=list)
    filtered: bool = False
    filter_reason: str = ""
    dedup_hash: Optional[str] = None


@dataclass
class FilterResult:
    """过滤结果"""
    content: ContentInfo
    allowed: bool
    action: FilterAction
    score: float
    quality_level: ContentQuality
    size: Optional[str] = ""  # 文件大小信息
    reasons: List[str] = field(default_factory=list)
    priority: int = 0
    tags: List[str] = field(default_factory=list)


class IntelligentFilter:
    """
    智能内容过滤器

    提供多维度的内容过滤和评分
    """

    def __init__(self):
        self.cache = get_global_cache()
        self.filtered_content: Set[str] = set()
        self.dedup_hashes: Set[str] = set()
        self.stats = {
            "total_checked": 0,
            "allowed": 0,
            "blocked": 0,
            "duplicates": 0,
            "excellent": 0,
            "good": 0,
            "average": 0,
            "poor": 0
        }

        # 格式优先级
        self.format_priority = {
            # 视频格式
            '.mkv': 100,
            '.mp4': 90,
            '.avi': 80,
            '.mov': 70,
            '.wmv': 60,
            '.flv': 50,

            # 音频格式
            '.flac': 100,
            '.mp3': 80,
            '.wav': 90,
            '.aac': 70,
            '.ogg': 60,

            # 压缩格式
            '.zip': 80,
            '.rar': 70,
            '.7z': 90,

            # 其他
            '.pdf': 50,
            '.epub': 60,
            '.mobi': 70
        }

        # 质量关键词
        self.quality_keywords = {
            'bluray': 50,
            'web-dl': 40,
            'dvdrip': 30,
            'ts': 10,
            'cam': 5,
            '4k': 40,
            '1080p': 30,
            '720p': 20,
            '480p': 10,
            'remux': 60,
            'repack': 30,
            'proper': 20
        }

        # 排除关键词
        self.exclude_keywords = [
            'xxx', 'adult', 'porn', 'sex',
            '广告', '推广', '广告位',
            'sample', 'trailer',
            'fake', '欺诈'
        ]

        # 默认过滤规则（必须在exclude_keywords之后）
        self.default_rules = self._load_default_rules()

    def _load_default_rules(self) -> List[FilterRule]:
        """加载默认过滤规则"""
        rules = [
            # 大小过滤
            FilterRule(
                name="min_size",
                action=FilterAction.BLOCK,
                pattern="10MB",
                pattern_type="size",
                priority=100,
                description="过滤小于10MB的文件"
            ),
            FilterRule(
                name="max_size",
                action=FilterAction.BLOCK,
                pattern="50GB",
                pattern_type="size",
                priority=90,
                description="过滤大于50GB的文件"
            ),
            # 做种数过滤
            FilterRule(
                name="min_seeders",
                action=FilterAction.BLOCK,
                pattern="5",
                pattern_type="seeders",
                priority=80,
                description="过滤做种数小于5的资源"
            ),
            # 关键词过滤
            FilterRule(
                name="exclude_keywords",
                action=FilterAction.BLOCK,
                pattern="|".join(self.exclude_keywords),
                pattern_type="keyword",
                priority=70,
                description="过滤包含不当关键词的资源"
            ),
            # 优先级
            FilterRule(
                name="high_quality",
                action=FilterAction.PRIORITY,
                pattern="bluray|4k|remux",
                pattern_type="keyword",
                priority=50,
                description="高质量资源优先"
            )
        ]
        return rules

    def add_rule(self, rule: FilterRule):
        """添加过滤规则"""
        self.default_rules.append(rule)
        logger.info(f"添加过滤规则: {rule.name}")

    def remove_rule(self, name: str):
        """移除过滤规则"""
        self.default_rules = [r for r in self.default_rules if r.name != name]
        logger.info(f"移除过滤规则: {name}")

    def parse_size(self, size_str: str) -> int:
        """解析大小字符串"""
        size_str = size_str.upper().strip()

        # 提取数字和单位
        match = re.match(r'([\d.]+)\s*(B|KB|MB|GB|TB)', size_str)
        if not match:
            return 0

        value, unit = match.groups()
        value = float(value)

        multipliers = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 ** 2,
            'GB': 1024 ** 3,
            'TB': 1024 ** 4
        }

        return int(value * multipliers.get(unit, 1))

    def calculate_quality_score(self, content: ContentInfo) -> Tuple[float, ContentQuality]:
        """计算内容质量分数 (0-100)"""
        score = 0.0

        # 1. 做种数评分 (0-40分)
        if content.seeders >= 100:
            score += 40
        elif content.seeders >= 50:
            score += 35
        elif content.seeders >= 20:
            score += 30
        elif content.seeders >= 10:
            score += 25
        elif content.seeders >= 5:
            score += 20
        elif content.seeders > 0:
            score += 10

        # 2. 健康度评分 (0-20分)
        total_peers = content.seeders + content.leechers
        if total_peers > 0:
            health_ratio = content.seeders / total_peers
            score += health_ratio * 20

        # 3. 文件大小评分 (0-15分)
        if content.size:
            # 电影类：500MB-10GB为佳
            if 500 * 1024 * 1024 <= content.size <= 10 * 1024 * 1024 * 1024:
                score += 15
            elif content.size > 0:
                score += 10

        # 4. 质量关键词评分 (0-25分)
        title_lower = content.title.lower()
        for keyword, points in self.quality_keywords.items():
            if keyword in title_lower:
                score += points

        # 5. 格式评分 (0-10分)
        for ext, points in self.format_priority.items():
            if ext in title_lower:
                score += min(points / 10, 10)
                break

        # 确保分数在0-100范围内
        score = max(0, min(100, score))

        # 确定质量等级
        if score >= 80:
            quality = ContentQuality.EXCELLENT
        elif score >= 60:
            quality = ContentQuality.GOOD
        elif score >= 40:
            quality = ContentQuality.AVERAGE
        elif score >= 20:
            quality = ContentQuality.POOR
        else:
            quality = ContentQuality.REJECT

        return score, quality

    def generate_dedup_hash(self, content: ContentInfo) -> str:
        """生成去重哈希"""
        # 基于标题和大小生成哈希
        dedup_str = f"{content.title.lower().strip()}:{content.size or 0}"
        return hashlib.md5(dedup_str.encode()).hexdigest()

    def is_duplicate(self, content: ContentInfo) -> bool:
        """检查是否重复"""
        # 生成去重哈希
        dedup_hash = self.generate_dedup_hash(content)
        content.dedup_hash = dedup_hash

        # 检查缓存
        cache_key = f"dedup:{dedup_hash}"
        if dedup_hash in self.dedup_hashes:
            return True

        # 检查缓存
        cached = self.cache.get(cache_key)
        if cached:
            return True

        # 记录到缓存（7天）
        self.dedup_hashes.add(dedup_hash)
        self.cache.set(cache_key, True, ttl=604800)

        return False

    def check_similarity(self, content1: str, content2: str) -> float:
        """检查两个内容的相似度"""
        return SequenceMatcher(None, content1.lower(), content2.lower()).ratio()

    def apply_filter_rules(self, content: ContentInfo) -> FilterResult:
        """应用过滤规则"""
        # 将size转换为字符串格式
        size_str = ""
        if content.size:
            if content.size >= 1024**3:  # >= 1GB
                size_str = f"{content.size / (1024**3):.1f}GB"
            elif content.size >= 1024**2:  # >= 1MB
                size_str = f"{content.size / (1024**2):.1f}MB"
            else:
                size_str = f"{content.size}B"
        
        result = FilterResult(
            content=content,
            allowed=True,
            action=FilterAction.ALLOW,
            score=content.quality_score,
            quality_level=content.quality_level,
            size=size_str
        )

        for rule in sorted(self.default_rules, key=lambda r: r.priority, reverse=True):
            if not rule.enabled:
                continue

            if rule.pattern_type == 'keyword':
                # 关键词匹配
                pattern_lower = rule.pattern.lower()
                title_lower = content.title.lower()

                if rule.action == FilterAction.BLOCK:
                    if any(keyword in title_lower for keyword in pattern_lower.split('|')):
                        result.allowed = False
                        result.action = FilterAction.BLOCK
                        result.reasons.append(f"包含阻止关键词: {rule.name}")
                        break
                elif rule.action == FilterAction.PRIORITY:
                    if any(keyword in title_lower for keyword in pattern_lower.split('|')):
                        result.priority += rule.priority
                        result.tags.append(f"priority:{rule.name}")

            elif rule.pattern_type == 'size' and content.size:
                # 大小匹配
                rule_size = self.parse_size(rule.pattern)
                if rule.action == FilterAction.BLOCK:
                    if rule.name == 'min_size' and content.size < rule_size:
                        result.allowed = False
                        result.action = FilterAction.BLOCK
                        result.reasons.append(f"文件过小 (< {rule.pattern})")
                        break
                    elif rule.name == 'max_size' and content.size > rule_size:
                        result.allowed = False
                        result.action = FilterAction.BLOCK
                        result.reasons.append(f"文件过大 (> {rule.pattern})")
                        break

            elif rule.pattern_type == 'seeders':
                # 做种数匹配
                min_seeders = int(rule.pattern)
                if rule.action == FilterAction.BLOCK:
                    if content.seeders < min_seeders:
                        result.allowed = False
                        result.action = FilterAction.BLOCK
                        result.reasons.append(f"做种数不足 (< {min_seeders})")
                        break

        return result

    def extract_tags(self, content: ContentInfo) -> List[str]:
        """提取内容标签"""
        tags = []
        title_lower = content.title.lower()

        # 质量标签
        for keyword, _ in self.quality_keywords.items():
            if keyword in title_lower:
                tags.append(f"quality:{keyword}")

        # 格式标签
        for ext, _ in self.format_priority.items():
            if ext in title_lower:
                tags.append(f"format:{ext[1:]}")

        # 分类标签
        if content.category:
            tags.append(f"category:{content.category}")

        # 大小标签
        if content.size:
            if content.size < 100 * 1024 * 1024:  # < 100MB
                tags.append("size:small")
            elif content.size > 10 * 1024 * 1024 * 1024:  # > 10GB
                tags.append("size:large")

        return tags

    async def filter_content(
        self,
        title: str,
        magnet_link: str,
        size: Optional[Union[str, int]] = None,
        seeders: int = 0,
        leechers: int = 0,
        category: str = ""
    ) -> FilterResult:
        """过滤内容"""
        self.stats["total_checked"] += 1

        # 解析磁力链接
        torrent_hash, _ = parse_magnet(magnet_link)

        # 标准化大小
        if isinstance(size, str):
            size_bytes = self.parse_size(size)
        elif isinstance(size, int):
            size_bytes = size
        else:
            size_bytes = None

        # 创建内容信息
        content = ContentInfo(
            title=title,
            magnet_link=magnet_link,
            size=size_bytes,
            seeders=seeders,
            leechers=leechers,
            category=category,
            hash=torrent_hash
        )

        # 检查重复
        if self.is_duplicate(content):
            self.stats["duplicates"] += 1
            # 生成size字符串
            size_str = ""
            if content.size:
                if content.size >= 1024**3:  # >= 1GB
                    size_str = f"{content.size / (1024**3):.1f}GB"
                elif content.size >= 1024**2:  # >= 1MB
                    size_str = f"{content.size / (1024**2):.1f}MB"
                else:
                    size_str = f"{content.size}B"
            
            result = FilterResult(
                content=content,
                allowed=False,
                action=FilterAction.BLOCK,
                score=0.0,
                quality_level=ContentQuality.REJECT,
                size=size_str,
                reasons=["重复内容"]
            )
            return result

        # 计算质量分数
        score, quality = self.calculate_quality_score(content)
        content.quality_score = score
        content.quality_level = quality

        # 提取标签
        tags = self.extract_tags(content)
        content.tags = tags

        # 应用过滤规则
        result = self.apply_filter_rules(content)

        # 更新统计
        if result.allowed:
            self.stats["allowed"] += 1
        else:
            self.stats["blocked"] += 1

        if quality == ContentQuality.EXCELLENT:
            self.stats["excellent"] += 1
        elif quality == ContentQuality.GOOD:
            self.stats["good"] += 1
        elif quality == ContentQuality.AVERAGE:
            self.stats["average"] += 1
        else:
            self.stats["poor"] += 1

        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取过滤统计"""
        total = max(1, self.stats["total_checked"])
        return {
            **self.stats,
            "allow_rate": self.stats["allowed"] / total * 100,
            "block_rate": self.stats["blocked"] / total * 100,
            "duplicate_rate": self.stats["duplicates"] / total * 100,
            "excellent_rate": self.stats["excellent"] / total * 100,
            "good_rate": self.stats["good"] / total * 100
        }

    def export_rules(self) -> List[Dict[str, Any]]:
        """导出过滤规则"""
        return [
            {
                "name": r.name,
                "action": r.action.value,
                "pattern": r.pattern,
                "pattern_type": r.pattern_type,
                "priority": r.priority,
                "enabled": r.enabled,
                "description": r.description
            }
            for r in self.default_rules
        ]

    def import_rules(self, rules_data: List[Dict[str, Any]]):
        """导入过滤规则"""
        for rule_data in rules_data:
            rule = FilterRule(
                name=rule_data["name"],
                action=FilterAction(rule_data["action"]),
                pattern=rule_data["pattern"],
                pattern_type=rule_data["pattern_type"],
                priority=rule_data.get("priority", 0),
                enabled=rule_data.get("enabled", True),
                description=rule_data.get("description", "")
            )
            self.add_rule(rule)


# 全局智能过滤器实例
_intelligent_filter: Optional[IntelligentFilter] = None


def get_intelligent_filter() -> IntelligentFilter:
    """获取全局智能过滤器"""
    global _intelligent_filter
    if _intelligent_filter is None:
        _intelligent_filter = IntelligentFilter()
    return _intelligent_filter


async def filter_magnet_link(
    title: str,
    magnet_link: str,
    **kwargs
) -> FilterResult:
    """过滤磁力链接的便捷函数"""
    filter_instance = get_intelligent_filter()
    return await filter_instance.filter_content(title, magnet_link, **kwargs)
