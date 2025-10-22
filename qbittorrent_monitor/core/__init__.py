"""
核心模块包初始化文件

提供高性能的磁力链接解析、剪贴板监控和缓存系统。
"""

from .local_processor import LocalClipboardProcessor, LocalCategoryMapper, LocalDuplicateDetector, create_local_processor
from .api_compliant_client import APIClient, create_api_client

__all__ = [
    'LocalClipboardProcessor',
    'LocalCategoryMapper',
    'LocalDuplicateDetector',
    'create_local_processor',
    'APIClient',
    'create_api_client'
]