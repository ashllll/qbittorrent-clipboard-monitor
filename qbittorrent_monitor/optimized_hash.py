"""优化的哈希模块 - 使用 xxHash"""
import hashlib
from typing import Optional

try:
    import xxhash
    XXHASH_AVAILABLE = True
except ImportError:
    XXHASH_AVAILABLE = False


class FastHasher:
    """高性能哈希计算器
    
    使用 xxHash（如果可用）或回退到 MD5
    xxHash 比 MD5 快 3-5 倍，且冲突率极低
    """
    
    def __init__(self):
        self._use_xxhash = XXHASH_AVAILABLE
        
    def hash_string(self, content: str, seed: int = 0) -> str:
        """计算字符串哈希
        
        Args:
            content: 要哈希的字符串
            seed: 哈希种子（用于不同用途的哈希）
            
        Returns:
            16进制哈希字符串
        """
        encoded = content.encode('utf-8')
        
        if self._use_xxhash:
            # xxHash64 比 MD5 快 3-5 倍
            return xxhash.xxh64(encoded, seed=seed).hexdigest()
        else:
            return hashlib.md5(encoded).hexdigest()
    
    def hash_string_32(self, content: str, seed: int = 0) -> str:
        """计算32位哈希（更快，适用于缓存键）"""
        encoded = content.encode('utf-8')
        
        if self._use_xxhash:
            return xxhash.xxh32(encoded, seed=seed).hexdigest()
        else:
            # 使用 MD5 前8位
            return hashlib.md5(encoded).hexdigest()[:8]
    
    def hash_bytes(self, data: bytes, seed: int = 0) -> str:
        """直接计算字节哈希"""
        if self._use_xxhash:
            return xxhash.xxh64(data, seed=seed).hexdigest()
        else:
            return hashlib.md5(data).hexdigest()
    
    @property
    def algorithm(self) -> str:
        """返回当前使用的算法名称"""
        return "xxhash" if self._use_xxhash else "md5"


# 全局单例
_hasher = FastHasher()
hash_string = _hasher.hash_string
hash_string_32 = _hasher.hash_string_32
hash_bytes = _hasher.hash_bytes


# ========== 磁力链接专用哈希优化 ==========

from collections import OrderedDict
from typing import Any, Dict, Optional
import re


class MagnetHashCache:
    """优化的磁力链接哈希缓存
    
    利用磁力链接自身的 btih 作为自然哈希，避免重复计算
    """
    
    # 预编译正则
    _BTIH_PATTERN = re.compile(r'btih:([a-fA-F0-9]{40}|[a-z2-7]{32})', re.IGNORECASE)
    
    def __init__(self, max_size: int = 10000):
        self._max_size = max_size
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._hits = 0
        self._misses = 0
        
    def _get_natural_hash(self, content: str) -> Optional[str]:
        """提取磁力链接的自然哈希（btih）
        
        如果内容是磁力链接，直接使用 btih 作为哈希键
        避免对整个长字符串进行哈希计算
        """
        # 快速检查
        if not content or len(content) < 50:
            return None
        
        if not content.startswith('magnet:?'):
            return None
        
        # 提取 btih
        match = self._BTIH_PATTERN.search(content)
        if match:
            return match.group(1).lower()
        
        return None
    
    def get(self, content: str) -> Optional[Any]:
        """获取缓存值，优先使用自然哈希"""
        # 尝试提取自然哈希
        natural_hash = self._get_natural_hash(content)
        if natural_hash:
            key = f"magnet:{natural_hash}"
        else:
            # 非磁力链接使用普通哈希
            key = hash_string_32(content)
        
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        
        self._misses += 1
        return None
    
    def put(self, content: str, value: Any) -> None:
        """添加缓存"""
        natural_hash = self._get_natural_hash(content)
        if natural_hash:
            key = f"magnet:{natural_hash}"
        else:
            key = hash_string_32(content)
        
        self._cache[key] = value
        self._cache.move_to_end(key)
        
        # LRU 淘汰
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
    
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
            "algorithm": _hasher.algorithm,
        }
