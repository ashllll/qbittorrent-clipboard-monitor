"""分类配置模块

提供 CategoryConfig 数据类和验证逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..exceptions_unified import ConfigurationError
from ..security import validate_save_path
from .validators import validate_keywords_list


@dataclass
class CategoryConfig:
    """分类配置
    
    Attributes:
        save_path: 该分类的保存路径
        keywords: 匹配该分类的关键词列表
    
    Example:
        >>> config = CategoryConfig(
        ...     save_path="/downloads/movies",
        ...     keywords=["电影", "Movie", "1080p", "4K"]
        ... )
    """
    save_path: str = ""
    keywords: List[str] = field(default_factory=list)

    def validate(self, name: str) -> None:
        """验证分类配置
        
        Args:
            name: 分类名称
            
        Raises:
            ConfigurationError: 当配置项无效时抛出
        """
        # 使用安全模块验证保存路径
        validate_save_path(self.save_path, f"分类 '{name}' 的 save_path")
        
        # 验证关键词列表
        validate_keywords_list(self.keywords, name)


def get_default_categories() -> Dict[str, CategoryConfig]:
    """获取默认分类配置
    
    Returns:
        包含常用分类的字典
    """
    return {
        "movies": CategoryConfig(
            save_path="/downloads/movies",
            keywords=["电影", "Movie", "1080p", "4K", "BluRay", "WEB-DL"]
        ),
        "tv": CategoryConfig(
            save_path="/downloads/tv",
            keywords=["S01", "E01", "电视剧", "Series", "Season"]
        ),
        "anime": CategoryConfig(
            save_path="/downloads/anime",
            keywords=["动画", "Anime", "[GM-Team]"]
        ),
        "music": CategoryConfig(
            save_path="/downloads/music",
            keywords=["音乐", "Music", "FLAC", "MP3", "Album"]
        ),
        "software": CategoryConfig(
            save_path="/downloads/software",
            keywords=["软件", "Software", "Portable", "Crack"]
        ),
        "other": CategoryConfig(
            save_path="/downloads/other",
            keywords=[]
        ),
    }
