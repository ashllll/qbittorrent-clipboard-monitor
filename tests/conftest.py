"""
测试配置和共享工具
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(project_root))

# 导入版本信息
from qbittorrent_monitor import __version__


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def temp_config_dir():
    """创建临时配置目录"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        yield temp_path


@pytest.fixture
def mock_config_data():
    """模拟配置数据"""
    return {
        "qbittorrent": {
            "host": "localhost",
            "port": 8080,
            "username": "test_user",
            "password": "test_pass",
            "use_https": False,
            "verify_ssl": False
        },
        "deepseek": {
            "api_key": "test_api_key",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com"
        },
        "categories": {
            "电影": {
                "savePath": "/downloads/movies",
                "keywords": ["电影", "movie", "1080p", "720p"],
                "description": "电影类内容"
            },
            "电视剧": {
                "savePath": "/downloads/tv",
                "keywords": ["电视剧", "TV", "剧集", "连续剧"],
                "description": "电视剧类内容"
            }
        },
        "check_interval": 1.0,
        "log_level": "INFO",
        "log_file": "test.log"
    }


@pytest.fixture
def mock_magnet_link():
    """模拟磁力链接"""
    return "magnet:?xt=urn:btih:test_hash&dn=测试电影&tr=tracker1"


@pytest.fixture
def mock_torrent_info():
    """模拟种子信息"""
    return {
        "name": "测试电影.2024.1080p.BluRay.x264",
        "hash": "test_hash_123456",
        "size": 1073741824,  # 1GB
        "trackers": ["tracker1.example.com", "tracker2.example.com"]
    }


class AsyncContextManagerMock:
    """异步上下文管理器Mock"""

    def __init__(self, return_value=None, side_effect=None):
        self.return_value = return_value
        self.side_effect = side_effect
        self.enter_count = 0
        self.exit_count = 0

    async def __aenter__(self):
        self.enter_count += 1
        if self.side_effect:
            if isinstance(self.side_effect, Exception):
                raise self.side_effect
            return self.side_effect
        return self.return_value or Mock()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exit_count += 1
        return False


class MockQBittorrentClient:
    """模拟qBittorrent客户端"""

    def __init__(self, config=None, **kwargs):
        self.config = config
        self.logged_in = False
        self.categories = []
        self.added_torrents = []
        self.call_count = {
            'login': 0,
            'add_torrent': 0,
            'get_version': 0,
            'get_categories': 0
        }

    async def __aenter__(self):
        self.logged_in = True
        self.call_count['login'] += 1
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.logged_in = False
        return False

    async def login(self, username=None, password=None):
        self.logged_in = True
        return True

    async def get_version(self):
        self.call_count['get_version'] += 1
        return __version__

    async def get_categories(self):
        self.call_count['get_categories'] += 1
        return self.categories

    async def add_torrent(self, magnet_link, category=None, **kwargs):
        self.call_count['add_torrent'] += 1
        self.added_torrents.append({
            'magnet': magnet_link,
            'category': category,
            'kwargs': kwargs
        })
        return True

    async def ensure_categories(self, categories):
        self.categories.extend(categories.keys())
        return True


class MockAIClassifier:
    """模拟AI分类器"""

    def __init__(self, config=None):
        self.config = config
        self.classification_count = 0
        self.classification_history = []
        self.cache = {}

    async def classify(self, torrent_name, categories=None):
        self.classification_count += 1

        # 简单的基于关键词的模拟分类
        torrent_name_lower = torrent_name.lower()
        if any(keyword in torrent_name_lower for keyword in ['电影', 'movie', 'film']):
            category = "电影"
        elif any(keyword in torrent_name_lower for keyword in ['剧', 'tv', 'episode']):
            category = "电视剧"
        else:
            category = "其他"

        result = {'category': category, 'confidence': 0.9}
        self.classification_history.append({
            'torrent_name': torrent_name,
            'result': result
        })

        return result

    def get_stats(self):
        return {
            'total_classifications': self.classification_count,
            'cache_hits': 0,
            'history_count': len(self.classification_history)
        }

    def clear_cache(self):
        self.cache.clear()


class MockClipboardMonitor:
    """模拟剪贴板监控器"""

    def __init__(self, qbt_client=None, config=None):
        self.qbt_client = qbt_client
        self.config = config
        self.monitoring = False
        self.clipboard_history = []
        self.processed_count = 0
        self.stop_called = False

    async def start(self):
        self.monitoring = True
        return True

    def stop(self):
        self.monitoring = False
        self.stop_called = True

    def get_status(self):
        return {
            'monitoring': self.monitoring,
            'processed_count': self.processed_count,
            'history_count': len(self.clipboard_history),
            'stop_called': self.stop_called
        }


def assert_valid_log_entry(log_entry, expected_level=None, expected_message_part=None):
    """验证日志条目格式"""
    assert isinstance(log_entry, dict)
    assert 'timestamp' in log_entry
    assert 'level' in log_entry
    assert 'message' in log_entry

    if expected_level:
        assert log_entry['level'] == expected_level

    if expected_message_part:
        assert expected_message_part in log_entry['message']


def create_test_log_entries(count=5):
    """创建测试日志条目"""
    import datetime
    entries = []
    for i in range(count):
        entry = {
            'timestamp': datetime.datetime.now().isoformat(),
            'level': 'INFO' if i % 2 == 0 else 'ERROR',
            'message': f'Test log message {i}',
            'module': 'test_module',
            'function': 'test_function',
            'line_number': i + 1
        }
        entries.append(entry)
    return entries


def async_side_effect(*args, **kwargs):
    """创建异步副作用函数"""
    async def side_effect_func(*args, **kwargs):
        return kwargs.get('return_value', None)
    return side_effect_func