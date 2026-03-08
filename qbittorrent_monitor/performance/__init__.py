"""性能优化模块

提供高性能的实现替代默认实现。
"""

from .trie_classifier import TrieClassifier
from .batch_writer import BatchDatabaseWriter, BatchRecord

__all__ = [
    "TrieClassifier",
    "BatchDatabaseWriter",
    "BatchRecord",
]
