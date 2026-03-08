"""测试配置"""

from __future__ import annotations

import pytest
import asyncio
import sys
from typing import Generator, TYPE_CHECKING

if TYPE_CHECKING:
    from qbittorrent_monitor.config import Config


@pytest.fixture  # type: ignore[untyped-decorator]
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture  # type: ignore[untyped-decorator]
def mock_config() -> Config:
    """模拟配置 - 使用安全的路径"""
    from qbittorrent_monitor.config import Config, QBConfig, AIConfig, CategoryConfig
    
    return Config(
        qbittorrent=QBConfig(host="localhost", port=8080, username="admin", password="adminadmin"),
        ai=AIConfig(enabled=False),
        categories={
            "movies": CategoryConfig(save_path="/downloads/movies", keywords=["movie", "BluRay"]),
            "tv": CategoryConfig(save_path="/downloads/tv", keywords=["S01", "E01", "TV"]),
            "anime": CategoryConfig(save_path="/downloads/anime", keywords=["Anime"]),
            "music": CategoryConfig(save_path="/downloads/music", keywords=["Music", "FLAC"]),
            "software": CategoryConfig(save_path="/downloads/software", keywords=["Software"]),
            "games": CategoryConfig(save_path="/downloads/games", keywords=["Game"]),
            "books": CategoryConfig(save_path="/downloads/books", keywords=["PDF", "EPUB"]),
            "other": CategoryConfig(save_path="/downloads/other"),
        },
        check_interval=0.1,
    )
