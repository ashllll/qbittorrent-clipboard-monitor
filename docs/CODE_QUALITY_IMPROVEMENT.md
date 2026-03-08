# 代码质量改进报告

> **项目**: qBittorrent Clipboard Monitor v3.0  
> **日期**: 2026-03-08  
> **范围**: 核心模块代码质量提升

---

## 一、代码质量改进清单

### 1.1 魔法数字提取（优先级：高）

| 文件 | 魔法数字 | 建议常量名 | 说明 |
|------|----------|------------|------|
| `monitor.py:99` | `50` (MB) | `MAX_CLIPBOARD_MEMORY_MB` | 剪贴板内存限制 |
| `monitor.py:107` | `1000` | `CONTENT_HASH_SAMPLE_SIZE` | 哈希采样大小 |
| `monitor.py:128` | `10 * 1024 * 1024` | `MAX_CACHEABLE_CONTENT_SIZE` | 最大可缓存内容 |
| `monitor.py:191` | `50` | `MIN_MAGNET_LENGTH` | 磁力链接最小长度 |
| `monitor.py:287` | `10000` | `MAX_PROCESSED_CACHE_SIZE` | 已处理缓存上限 |
| `monitor.py:300` | `2.0` | `DEFAULT_DEBOUNCE_SECONDS` | 防抖时间窗口 |
| `monitor.py:303` | `100` | `MAX_MAGNETS_PER_CHECK` | 单次检查上限 |
| `monitor.py:538` | `0.5` | `CLIPBOARD_READ_TIMEOUT` | 剪贴板读取超时 |
| `monitor.py:705` | `50` | `MAX_LOG_NAME_LENGTH` | 日志名称截断长度 |
| `monitor.py:747` | `200` | `MAX_DB_NAME_LENGTH` | 数据库名称长度限制 |
| `classifier.py:41` | `1000` | `DEFAULT_CACHE_CAPACITY` | 默认缓存容量 |
| `classifier.py:207` | `5` | `DEFAULT_BATCH_CONCURRENCY` | 默认批处理并发数 |
| `classifier.py:260` | `0.5, 0.1, 0.8` | 置信度计算常量 | 需封装为配置 |
| `classifier.py:403` | `0.7` | `HIGH_CONFIDENCE_THRESHOLD` | 高置信度阈值 |
| `classifier.py:347` | `0.85` | `AI_BASE_CONFIDENCE` | AI基础置信度 |

### 1.2 类型注解完善（优先级：高）

**当前问题：**
1. 使用旧版 `Optional`, `List`, `Dict`, `Tuple` 而非 `| None`, `list`, `dict`, `tuple`
2. 部分函数缺少返回类型注解
3. 复杂类型可提取为类型别名

**改进方向：**
```python
# 改进前
from typing import Optional, List, Dict, Callable

def process(items: List[str]) -> Optional[Dict[str, Any]]:
    pass

# 改进后（Python 3.9+）
from typing import Callable, Any

def process(items: list[str]) -> dict[str, Any] | None:
    pass
```

### 1.3 函数拆分（优先级：高）

| 函数 | 当前行数 | 问题 | 拆分方案 |
|------|----------|------|----------|
| `_process_magnet` | ~130行 | 职责过多：验证→防抖→分类→添加→记录 | 拆分为5个子函数 |
| `_check_clipboard` | ~50行 | 混合剪贴板读取和哈希计算 | 拆分为读取和解析两个函数 |
| `_rule_classify` | ~35行 | 包含置信度计算和匹配逻辑 | 拆分为匹配和计算两个函数 |

### 1.4 依赖注入与接口抽象（优先级：中）

**当前问题：**
1. `ClipboardMonitor` 直接实例化 `ContentClassifier`
2. 数据库操作与业务逻辑紧密耦合
3. 指标收集使用全局模块

**改进方案：**
1. 定义 `IClassifier`, `IDatabase`, `IMetricsCollector` 接口
2. 通过构造函数注入依赖
3. 使用工厂模式创建实例

### 1.5 文档完善（优先级：中）

**需要补充文档的位置：**
1. 复杂算法（置信度计算、智能轮询）
2. 状态转换逻辑
3. 错误处理策略

---

## 二、重构前后代码对比示例

### 2.1 魔法数字提取

#### 改进前 (`monitor.py`)
```python
class ClipboardCache:
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 50):
        self._max_memory_bytes = max_memory_mb * 1024 * 1024
        
    def put(self, content: str, result_hash: str) -> None:
        content_size = len(content.encode('utf-8'))
        if content_size > 10 * 1024 * 1024:  # 10MB 限制
            return
```

#### 改进后 (`monitor.py`)
```python
# 在模块级别定义常量
MAX_CLIPBOARD_CACHE_SIZE = 1000  # 剪贴板缓存最大条目数
MAX_CLIPBOARD_MEMORY_MB = 50     # 剪贴板缓存最大内存（MB）
MAX_CACHEABLE_CONTENT_MB = 10    # 单个内容最大缓存大小（MB）
BYTES_PER_MB = 1024 * 1024

class ClipboardCache:
    """剪贴板内容哈希缓存 - 避免重复解析
    
    使用 MD5 哈希（缓存场景不需要加密安全）以获得更好性能。
    添加内存限制防止内存泄漏。
    
    Attributes:
        _max_size: 最大缓存条目数，默认 MAX_CLIPBOARD_CACHE_SIZE
        _max_memory_bytes: 最大内存限制（字节）
    """
    
    def __init__(
        self, 
        max_size: int = MAX_CLIPBOARD_CACHE_SIZE, 
        max_memory_mb: int = MAX_CLIPBOARD_MEMORY_MB
    ):
        self._cache: dict[str, str] = {}
        self._max_size = max_size
        self._access_times: dict[str, float] = {}
        self._max_memory_bytes = max_memory_mb * BYTES_PER_MB
        self._total_content_size = 0
        self._hash_hits = 0
        self._hash_misses = 0
    
    def put(self, content: str, result_hash: str) -> None:
        """添加缓存项，超过大小限制的内容将被忽略"""
        content_size = len(content.encode('utf-8'))
        if content_size > MAX_CACHEABLE_CONTENT_MB * BYTES_PER_MB:
            logger.debug(
                f"剪贴板内容过大 ({content_size} 字节)，"
                f"超过限制 {MAX_CACHEABLE_CONTENT_MB}MB，跳过缓存"
            )
            return
```

### 2.2 类型注解现代化

#### 改进前 (`classifier.py`)
```python
from typing import Dict, List, Optional, Tuple, Any

class ContentClassifier:
    DEFAULT_KEYWORDS: Dict[str, List[str]] = {...}
    
    def _rule_classify(self, name: str) -> Optional[ClassificationResult]:
        best_match: Optional[Tuple[str, float]] = None
        
    def classify_batch(
        self, 
        names: List[str], 
        use_cache: bool = True,
    ) -> List[ClassificationResult]:
```

#### 改进后 (`classifier.py`)
```python
from typing import Any
from collections.abc import Sequence

# 类型别名
CategoryName = str
KeywordList = list[str]
CategoryKeywords = dict[CategoryName, KeywordList]
MatchResult = tuple[CategoryName, float] | None

class ContentClassifier:
    DEFAULT_KEYWORDS: CategoryKeywords = {...}
    
    def _rule_classify(self, name: str) -> ClassificationResult | None:
        best_match: MatchResult = None
        
    def classify_batch(
        self, 
        names: Sequence[str],  # 更抽象的序列类型
        use_cache: bool = True,
    ) -> list[ClassificationResult]:
```

### 2.3 函数拆分（单一职责）

#### 改进前 (`monitor.py` - 130行的 `_process_magnet`)
```python
async def _process_magnet(self, magnet: str) -> None:
    """处理单个磁力链接 - 优化版，添加防抖"""
    self.stats.total_processed += 1
    
    # 1. 解析名称
    name: str = parse_magnet(magnet) or magnet
    
    # 2. 验证磁力链接
    is_valid, error = validate_magnet(magnet)
    if not is_valid:
        logger.warning(f"无效的磁力链接，跳过: {error}")
        self.stats.invalid_magnets += 1
        metrics_module.record_torrent_processed(category="invalid")
        # ... 30行记录无效链接的代码 ...
        return
    
    # 3. 提取 hash
    magnet_hash = extract_magnet_hash(magnet) or magnet
    
    # 4. 防抖检查
    now = time.time()
    if magnet_hash in self._pending_magnets:
        last_seen = self._pending_magnets[magnet_hash]
        if now - last_seen < self._debounce_seconds:
            logger.debug(f"磁力链接在防抖窗口内，跳过...")
            self.stats.duplicates_skipped += 1
            return
    self._pending_magnets[magnet_hash] = now
    self._cleanup_pending_magnets()
    
    # 5. 分类
    with metrics_module.timed_classification():
        classification_result = await self.classifier.classify(name)
    category = classification_result.category
    
    # 6. 重复检查
    if magnet_hash in self._processed:
        # ... 20行处理重复的代码 ...
        return
    
    # 7. 添加到 qBittorrent
    # ... 40行添加逻辑的代码 ...
```

#### 改进后 (`monitor.py` - 拆分为5个函数)
```python
# 定义常量
DEFAULT_DEBOUNCE_SECONDS = 2.0
MAX_PROCESSED_CACHE_SIZE = 10_000
MAX_LOG_NAME_LENGTH = 50
MAX_DB_NAME_LENGTH = 200

@dataclass
class MagnetProcessingContext:
    """磁力链接处理上下文"""
    magnet: str
    name: str
    magnet_hash: str
    category: str = ""
    status: str = "pending"


class ClipboardMonitor:
    # ... 其他代码 ...
    
    async def _process_magnet(self, magnet: str) -> None:
        """处理单个磁力链接 - 主流程协调器
        
        使用管道模式，将处理流程分解为独立的步骤，
        每个步骤可以独立测试和复用。
        """
        self.stats.total_processed += 1
        
        # 步骤1: 创建处理上下文
        ctx = self._create_processing_context(magnet)
        if ctx is None:
            return
        
        # 步骤2: 防抖检查
        if self._is_in_debounce_window(ctx.magnet_hash):
            self._handle_duplicate(ctx, reason="debounce")
            return
        
        # 步骤3: 检查是否已处理
        if self._is_already_processed(ctx.magnet_hash):
            await self._handle_already_processed(ctx)
            return
        
        # 步骤4: 分类内容
        ctx.category = await self._classify_content(ctx.name)
        
        # 步骤5: 添加到下载器并记录
        success = await self._add_to_downloader(ctx)
        await self._record_processing_result(ctx, success)
    
    def _create_processing_context(
        self, 
        magnet: str
    ) -> MagnetProcessingContext | None:
        """创建处理上下文，包含验证和初始化逻辑"""
        # 验证磁力链接
        is_valid, error = validate_magnet(magnet)
        if not is_valid:
            self._handle_invalid_magnet(magnet, error)
            return None
        
        name = parse_magnet(magnet) or magnet
        magnet_hash = extract_magnet_hash(magnet) or magnet
        
        return MagnetProcessingContext(
            magnet=magnet,
            name=name,
            magnet_hash=magnet_hash
        )
    
    def _is_in_debounce_window(self, magnet_hash: str) -> bool:
        """检查磁力链接是否在防抖窗口内"""
        now = time.time()
        last_seen = self._pending_magnets.get(magnet_hash)
        
        if last_seen and now - last_seen < self._debounce_seconds:
            return True
        
        self._pending_magnets[magnet_hash] = now
        self._cleanup_pending_magnets()
        return False
    
    def _is_already_processed(self, magnet_hash: str) -> bool:
        """检查磁力链接是否已处理过"""
        return magnet_hash in self._processed
    
    async def _classify_content(self, name: str) -> str:
        """对内容进行分类"""
        with metrics_module.timed_classification():
            result = await self.classifier.classify(name)
        
        # 记录分类指标
        metrics_module.record_classification(
            method=result.method,
            category=result.category
        )
        
        display_name = self._truncate_for_log(name, MAX_LOG_NAME_LENGTH)
        logger.info(f"分类: {display_name} -> {result.category}")
        
        return result.category
    
    async def _add_to_downloader(
        self, 
        ctx: MagnetProcessingContext
    ) -> bool:
        """将磁力链接添加到下载器"""
        cat_config = self.config.categories.get(ctx.category)
        
        with metrics_module.timed_torrent_add():
            return await self.qb.add_torrent(
                ctx.magnet,
                category=ctx.category,
                save_path=cat_config.save_path if cat_config else None
            )
    
    async def _record_processing_result(
        self, 
        ctx: MagnetProcessingContext, 
        success: bool
    ) -> None:
        """记录处理结果到统计和数据库"""
        if success:
            ctx.status = "success"
            self.stats.successful_adds += 1
            self._processed[ctx.magnet_hash] = None
            self._trim_processed_cache()
            metrics_module.record_torrent_added_success(category=ctx.category)
            self._trigger_handlers(ctx.magnet, ctx.category)
        else:
            ctx.status = "failed"
            self.stats.failed_adds += 1
            metrics_module.record_torrent_added_failed(
                category=ctx.category, 
                reason="api"
            )
        
        await self._persist_record(ctx)
    
    def _truncate_for_log(self, text: str, max_length: int) -> str:
        """截断文本用于日志显示"""
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text
    
    def _trim_processed_cache(self) -> None:
        """修剪已处理缓存，保持大小限制"""
        while len(self._processed) > MAX_PROCESSED_CACHE_SIZE:
            self._processed.popitem(last=False)
```

### 2.4 依赖注入与接口抽象

#### 改进前
```python
class ClipboardMonitor:
    def __init__(
        self, 
        qb_client: QBClient, 
        config: Config, 
        classifier: Optional[ContentClassifier] = None,
        database: Optional[DatabaseManager] = None,
    ):
        self.qb = qb_client
        self.config = config
        # 直接实例化或使用传入的参数
        self.classifier = classifier or ContentClassifier(config)
        self._db: Optional[DatabaseManager] = None
        self._external_db = database
```

#### 改进后
```python
from abc import ABC, abstractmethod
from typing import Protocol


class IClassifier(Protocol):
    """分类器接口"""
    
    async def classify(
        self, 
        name: str, 
        use_cache: bool = True
    ) -> ClassificationResult:
        """对内容进行分类"""
        ...


class IDatabase(Protocol):
    """数据库接口"""
    
    async def record_torrent(
        self,
        magnet_hash: str,
        name: str,
        category: str,
        status: str,
        error_message: str | None = None
    ) -> None:
        """记录种子信息"""
        ...


class IMetricsCollector(Protocol):
    """指标收集接口"""
    
    def record_torrent_processed(self, category: str) -> None: ...
    def record_torrent_added_success(self, category: str) -> None: ...
    def record_torrent_added_failed(
        self, 
        category: str, 
        reason: str
    ) -> None: ...


class ClipboardMonitor:
    """剪贴板监控器 - 依赖注入版本
    
    所有外部依赖通过构造函数注入，便于测试和替换实现。
    
    Args:
        qb_client: qBittorrent 客户端
        config: 应用配置
        classifier: 内容分类器（可选，默认创建）
        database: 数据库管理器（可选）
        metrics: 指标收集器（可选，默认使用全局）
        pacing_config: 轮询配置（可选）
    """
    
    def __init__(
        self, 
        qb_client: QBClient, 
        config: Config, 
        classifier: IClassifier | None = None,
        database: IDatabase | None = None,
        metrics: IMetricsCollector | None = None,
        pacing_config: PacingConfig | None = None,
    ):
        self.qb = qb_client
        self.config = config
        self.classifier = classifier or ContentClassifier(config)
        self.database = database
        self.metrics = metrics or metrics_module
        self.pacing = pacing_config or PacingConfig()
        
        # 初始化统计
        self.stats = MonitorStats()
        self._cache = ClipboardCache()
        self._processed: OrderedDict[str, None] = OrderedDict()
```

### 2.5 完善文档

#### 改进前
```python
def _calculate_rule_confidence(
    self, 
    name: str, 
    category: str, 
    matched_count: int = 1
) -> float:
    """计算规则分类的置信度 - 优化版"""
    keywords = self._keywords.get(category, [])
    
    if not keywords:
        return 0.5
    
    if matched_count == 0:
        return 0.0
    
    base_confidence = min(0.5 + matched_count * 0.1, 0.8)
    match_ratio = matched_count / len(keywords)
    ratio_bonus = min(match_ratio * 0.2, 0.15)
    
    return min(base_confidence + ratio_bonus, 0.95)
```

#### 改进后
```python
def _calculate_rule_confidence(
    self, 
    name: str, 
    category: str, 
    matched_count: int = 1
) -> float:
    """计算规则分类的置信度
    
    置信度计算基于以下因素：
    1. 匹配关键词数量：每多匹配一个关键词增加 0.1，上限 0.8
    2. 匹配比例：匹配数/总关键词数，乘以系数 0.2，上限 0.15
    3. 最终置信度 = min(基础置信度 + 比例加成, 0.95)
    
    公式：
        base = min(0.5 + matches * 0.1, 0.8)
        bonus = min((matches / total) * 0.2, 0.15)
        confidence = min(base + bonus, 0.95)
    
    Args:
        name: 内容名称（保留用于未来扩展，如基于名称长度加权）
        category: 分类名称
        matched_count: 匹配的关键词数量
        
    Returns:
        0.0-0.95 之间的置信度分数
        
    Example:
        >>> classifier._calculate_rule_confidence("Movie 1080p", "movies", 2)
        0.7  # 基础 0.5 + 2*0.1 = 0.7，假设匹配比例低无加成
    """
    keywords = self._keywords.get(category, [])
    
    if not keywords:
        return 0.5  # 无关键词配置时的默认置信度
    
    if matched_count == 0:
        return 0.0  # 无匹配时置信度为0
    
    # 基础置信度：0.5 起点，每匹配一个 +0.1，上限 0.8
    base_confidence = min(
        CONFIDENCE_BASE + matched_count * CONFIDENCE_PER_MATCH,
        CONFIDENCE_BASE_MAX
    )
    
    # 匹配比例加成：匹配比例 * 0.2，上限 0.15
    match_ratio = matched_count / len(keywords)
    ratio_bonus = min(
        match_ratio * CONFIDENCE_RATIO_MULTIPLIER,
        CONFIDENCE_RATIO_CAP
    )
    
    return min(
        base_confidence + ratio_bonus,
        CONFIDENCE_MAX
    )
```

---

## 三、接口设计文档

### 3.1 核心接口定义

```python
# interfaces.py
from typing import Protocol, runtime_checkable
from collections.abc import Sequence, Callable
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ClassificationResult:
    """分类结果 - 不可变数据类"""
    category: str
    confidence: float  # 0.0-1.0
    method: str        # "rule", "ai", "fallback"
    cached: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        # 验证置信度范围
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"置信度必须在 0.0-1.0 之间，当前: {self.confidence}")


@runtime_checkable
class IClassifier(Protocol):
    """内容分类器接口"""
    
    async def classify(
        self, 
        name: str, 
        use_cache: bool = True,
        timeout: float | None = None
    ) -> ClassificationResult:
        """对单个内容进行分类"""
        ...
    
    async def classify_batch(
        self, 
        names: Sequence[str],
        max_concurrent: int = 5
    ) -> list[ClassificationResult]:
        """批量分类内容"""
        ...
    
    def get_cache_stats(self) -> dict[str, float]:
        """获取缓存统计信息"""
        ...


@runtime_checkable
class ITorrentClient(Protocol):
    """Torrent 客户端接口"""
    
    async def add_torrent(
        self,
        magnet: str,
        category: str | None = None,
        save_path: str | None = None
    ) -> bool:
        """添加磁力链接"""
        ...
    
    async def get_categories(self) -> dict[str, dict]:
        """获取所有分类"""
        ...
    
    async def create_category(self, name: str, save_path: str) -> bool:
        """创建分类"""
        ...
    
    async def is_connected(self) -> bool:
        """检查连接状态"""
        ...


@runtime_checkable
class IClipboardProvider(Protocol):
    """剪贴板访问接口（便于测试时 mock）"""
    
    def get_content(self) -> str:
        """获取当前剪贴板内容"""
        ...
    
    def set_content(self, content: str) -> None:
        """设置剪贴板内容"""
        ...


@runtime_checkable
class IDatabase(Protocol):
    """数据持久化接口"""
    
    async def record_torrent(
        self,
        magnet_hash: str,
        name: str,
        category: str,
        status: str,  # "success", "failed", "duplicate", "invalid"
        error_message: str | None = None
    ) -> None:
        """记录种子处理结果"""
        ...
    
    async def get_torrent_history(
        self,
        category: str | None = None,
        status: str | None = None,
        limit: int = 100
    ) -> list[dict]:
        """查询历史记录"""
        ...
    
    async def is_processed(self, magnet_hash: str) -> bool:
        """检查是否已处理过"""
        ...


@runtime_checkable
class IMetricsCollector(Protocol):
    """指标收集接口"""
    
    def record_clipboard_change(self) -> None: ...
    def record_torrent_processed(self, category: str) -> None: ...
    def record_torrent_added_success(self, category: str) -> None: ...
    def record_torrent_added_failed(
        self, 
        category: str, 
        reason: str
    ) -> None: ...
    def record_duplicate_skipped(self, reason: str) -> None: ...
    def record_classification(
        self, 
        method: str, 
        category: str
    ) -> None: ...
    def timed_classification(self): ...
    def timed_torrent_add(self): ...
```

### 3.2 依赖注入容器（简化版）

```python
# container.py
from dataclasses import dataclass
from typing import TypeVar, Generic

T = TypeVar('T')


@dataclass
class ServiceConfig:
    """服务配置"""
    use_mock_clipboard: bool = False
    use_mock_database: bool = False
    disable_metrics: bool = False


class ServiceContainer:
    """服务容器 - 管理依赖生命周期"""
    
    def __init__(self, config: Config, service_config: ServiceConfig | None = None):
        self.config = config
        self.service_config = service_config or ServiceConfig()
        self._services: dict[type, object] = {}
    
    def get_classifier(self) -> IClassifier:
        """获取分类器实例"""
        if IClassifier not in self._services:
            self._services[IClassifier] = ContentClassifier(self.config)
        return self._services[IClassifier]  # type: ignore
    
    def get_database(self) -> IDatabase | None:
        """获取数据库实例"""
        if not self.config.database.enabled:
            return None
        
        if IDatabase not in self._services:
            if self.service_config.use_mock_database:
                from tests.mocks import MockDatabase
                self._services[IDatabase] = MockDatabase()
            else:
                self._services[IDatabase] = DatabaseManager(
                    self.config.database.db_path
                )
        return self._services[IDatabase]  # type: ignore
    
    def get_clipboard_provider(self) -> IClipboardProvider:
        """获取剪贴板提供器"""
        if IClipboardProvider not in self._services:
            if self.service_config.use_mock_clipboard:
                from tests.mocks import MockClipboard
                self._services[IClipboardProvider] = MockClipboard()
            else:
                self._services[IClipboardProvider] = PyperclipProvider()
        return self._services[IClipboardProvider]  # type: ignore
    
    def create_monitor(self) -> ClipboardMonitor:
        """创建监控器实例"""
        return ClipboardMonitor(
            qb_client=QBClient(self.config),
            config=self.config,
            classifier=self.get_classifier(),
            database=self.get_database(),
            metrics=None if self.service_config.disable_metrics else metrics_module,
        )
```

---

## 四、测试覆盖建议

### 4.1 当前测试覆盖情况

| 模块 | 当前状态 | 建议覆盖率 |
|------|----------|------------|
| `config.py` | 中等 | 90%+ |
| `classifier.py` | 中等 | 90%+ |
| `monitor.py` | 低 | 85%+ |
| `qb_client.py` | 低 | 80%+ |
| `utils.py` | 高 | 保持 |
| `security.py` | 中等 | 90%+ |

### 4.2 新增测试用例建议

#### 单元测试 - 分类器
```python
# test_classifier_unit.py
class TestRuleClassifierUnit:
    """规则分类器单元测试"""
    
    def test_calculate_confidence_no_keywords(self):
        """测试无关键词时的默认置信度"""
        classifier = ContentClassifier(MockConfig())
        confidence = classifier._calculate_rule_confidence("test", "empty", 0)
        assert confidence == 0.0
    
    def test_calculate_confidence_single_match(self):
        """测试单关键词匹配的置信度计算"""
        classifier = ContentClassifier(MockConfig())
        confidence = classifier._calculate_rule_confidence(
            "test", "movies", matched_count=1
        )
        assert confidence == 0.6  # 0.5 + 0.1
    
    def test_calculate_confidence_max_cap(self):
        """测试置信度上限"""
        classifier = ContentClassifier(MockConfig())
        confidence = classifier._calculate_rule_confidence(
            "test", "movies", matched_count=100
        )
        assert confidence <= 0.95  # 上限检查
```

#### 单元测试 - 防抖逻辑
```python
# test_debounce.py
class TestDebounceLogic:
    """防抖机制单元测试"""
    
    @pytest.mark.asyncio
    async def test_debounce_window_blocks_duplicate(self):
        """测试防抖窗口阻止重复"""
        monitor = create_test_monitor(debounce_seconds=1.0)
        
        # 第一次处理
        result1 = await monitor._process_magnet("magnet:?xt=urn:btih:test123")
        assert result1 is not None
        
        # 立即第二次处理（应在防抖窗口内）
        result2 = await monitor._process_magnet("magnet:?xt=urn:btih:test123")
        assert result2 is None  # 被防抖阻止
    
    @pytest.mark.asyncio
    async def test_debounce_expires_after_timeout(self):
        """测试防抖超时后允许处理"""
        monitor = create_test_monitor(debounce_seconds=0.1)
        
        await monitor._process_magnet("magnet:?xt=urn:btih:test123")
        await asyncio.sleep(0.2)  # 等待防抖过期
        
        result = await monitor._process_magnet("magnet:?xt=urn:btih:test123")
        assert result is not None
```

#### 集成测试 - 完整流程
```python
# test_integration.py
class TestProcessingPipeline:
    """处理管道集成测试"""
    
    @pytest.mark.asyncio
    async def test_full_processing_flow(self):
        """测试完整的处理流程"""
        # 准备
        mock_qb = MockQBClient()
        mock_db = MockDatabase()
        classifier = ContentClassifier(MockConfig())
        
        monitor = ClipboardMonitor(
            qb_client=mock_qb,
            config=MockConfig(),
            classifier=classifier,
            database=mock_db,
            metrics=MockMetrics()
        )
        
        # 执行
        magnet = "magnet:?xt=urn:btih:1234567890abcdef&dn=Test.Movie.1080p"
        await monitor._process_magnet(magnet)
        
        # 验证
        assert mock_qb.added_torrents == [magnet]
        assert mock_db.records[0]["category"] == "movies"
        assert mock_db.records[0]["status"] == "success"
```

### 4.3 Mock 类设计

```python
# tests/mocks.py
class MockQBClient:
    """Mock qBittorrent 客户端"""
    
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.added_torrents: list[str] = []
        self.categories: dict[str, dict] = {}
    
    async def add_torrent(
        self,
        magnet: str,
        category: str | None = None,
        save_path: str | None = None
    ) -> bool:
        self.added_torrents.append({
            "magnet": magnet,
            "category": category,
            "save_path": save_path
        })
        return self.should_succeed
    
    async def get_categories(self) -> dict[str, dict]:
        return self.categories


class MockDatabase:
    """Mock 数据库"""
    
    def __init__(self):
        self.records: list[dict] = []
        self.processed_hashes: set[str] = set()
    
    async def record_torrent(
        self,
        magnet_hash: str,
        name: str,
        category: str,
        status: str,
        error_message: str | None = None
    ) -> None:
        self.records.append({
            "magnet_hash": magnet_hash,
            "name": name,
            "category": category,
            "status": status,
            "error_message": error_message
        })
        if status in ("success", "duplicate"):
            self.processed_hashes.add(magnet_hash)
    
    async def is_processed(self, magnet_hash: str) -> bool:
        return magnet_hash in self.processed_hashes


class MockClipboard:
    """Mock 剪贴板"""
    
    def __init__(self, initial_content: str = ""):
        self._content = initial_content
        self.history: list[str] = []
    
    def get_content(self) -> str:
        return self._content
    
    def set_content(self, content: str) -> None:
        self.history.append(content)
        self._content = content
    
    def simulate_copy(self, content: str) -> None:
        """模拟用户复制操作"""
        self.set_content(content)
```

---

## 五、实施建议

### 5.1 实施顺序

```
Phase 1: 低风险改进（1-2天）
├── 提取魔法数字为常量
├── 完善类型注解
└── 补充文档字符串

Phase 2: 中等风险改进（2-3天）
├── 拆分过长函数
├── 定义接口协议
└── 更新现有测试

Phase 3: 架构改进（3-5天）
├── 实现依赖注入
├── 重构核心类
└── 新增测试覆盖
```

### 5.2 风险评估

| 改进项 | 风险等级 | 回滚难度 | 测试要求 |
|--------|----------|----------|----------|
| 魔法数字提取 | 低 | 容易 | 现有测试通过 |
| 类型注解完善 | 低 | 容易 | mypy 检查通过 |
| 函数拆分 | 中 | 中等 | 新增单元测试 |
| 依赖注入 | 中 | 较难 | 完整集成测试 |
| 接口抽象 | 中 | 中等 | 接口兼容性测试 |

### 5.3 预期收益

1. **可维护性**: 代码结构更清晰，修改更 confidently
2. **可测试性**: 依赖注入使单元测试覆盖率提升至 85%+
3. **类型安全**: mypy 严格模式检查通过，减少运行时错误
4. **文档质量**: 新开发者上手时间减少 50%

---

## 六、附录：完整常量定义

```python
# constants.py

# 剪贴板监控常量
class MonitorConstants:
    """剪贴板监控相关常量"""
    
    # 缓存配置
    DEFAULT_CACHE_SIZE = 1000
    DEFAULT_CACHE_MEMORY_MB = 50
    MAX_CACHEABLE_CONTENT_MB = 10
    BYTES_PER_MB = 1024 * 1024
    
    # 处理限制
    MAX_PROCESSED_CACHE_SIZE = 10_000
    MAX_MAGNETS_PER_CHECK = 100
    MAX_LOG_NAME_LENGTH = 50
    MAX_DB_NAME_LENGTH = 200
    
    # 时间配置（秒）
    DEFAULT_DEBOUNCE_SECONDS = 2.0
    CLIPBOARD_READ_TIMEOUT = 0.5
    DEBOUNCE_CLEANUP_MULTIPLIER = 2.0
    
    # 磁力链接限制
    MIN_MAGNET_LENGTH = 50
    CONTENT_HASH_SAMPLE_SIZE = 1000


# 分类器常量
class ClassifierConstants:
    """内容分类器相关常量"""
    
    # 缓存配置
    DEFAULT_CACHE_CAPACITY = 1000
    DEFAULT_BATCH_CONCURRENCY = 5
    
    # 置信度计算
    CONFIDENCE_BASE = 0.5
    CONFIDENCE_PER_MATCH = 0.1
    CONFIDENCE_BASE_MAX = 0.8
    CONFIDENCE_RATIO_MULTIPLIER = 0.2
    CONFIDENCE_RATIO_CAP = 0.15
    CONFIDENCE_MAX = 0.95
    
    # 阈值
    HIGH_CONFIDENCE_THRESHOLD = 0.7
    AI_BASE_CONFIDENCE = 0.85
    FALLBACK_CONFIDENCE = 0.3
    
    # AI 配置
    DEFAULT_AI_TIMEOUT = 30.0
    DEFAULT_AI_TEMPERATURE = 0.3
    DEFAULT_AI_MAX_TOKENS = 20


# 智能轮询常量
class PacingConstants:
    """智能轮询相关常量"""
    
    DEFAULT_ACTIVE_INTERVAL = 0.5
    DEFAULT_IDLE_INTERVAL = 3.0
    DEFAULT_IDLE_THRESHOLD = 30.0
    DEFAULT_BURST_WINDOW = 5.0
    DEFAULT_BURST_THRESHOLD = 3


# HTTP 状态码
class HTTPStatus:
    """HTTP 状态码常量"""
    OK = 200
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    SERVER_ERROR_START = 500
```

---

*本报告由代码质量代理生成，旨在提升项目可维护性和可测试性。*
