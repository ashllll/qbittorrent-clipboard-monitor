# qBittorrent Clipboard Monitor API 文档

## 概述

qBittorrent Clipboard Monitor 是一个企业级的自动化下载管理工具，主要用于监控剪贴板中的磁力链接和网页URL，自动将种子添加到qBittorrent客户端并进行智能分类。本文档详细描述了项目的API接口和使用方法。

## 目录

- [配置管理 API](#配置管理-api)
- [qBittorrent 客户端 API](#qbittorrent-客户端-api)
- [AI 分类器 API](#ai-分类器-api)
- [剪贴板监控器 API](#剪贴板监控器-api)
- [网页爬虫 API](#网页爬虫-api)
- [工具函数 API](#工具函数-api)
- [通知系统 API](#通知系统-api)

## 配置管理 API

### ConfigManager

配置管理器负责加载和管理应用程序配置。

#### 类方法

##### `__init__(self, config_path: Optional[Union[str, Path]] = None)`

初始化配置管理器。

**参数:**
- `config_path`: 配置文件路径，可选，默认为脚本同目录下的config.json

**返回:**
- 无

##### `async def load_config(self) -> AppConfig`

加载并验证配置文件。

**参数:**
- 无

**返回:**
- `AppConfig`: 应用程序配置对象

**异常:**
- `ConfigError`: 配置加载失败时抛出

##### `async def reload_config(self)`

重新加载配置。

**参数:**
- 无

**返回:**
- 无

##### `def register_reload_callback(self, callback: callable)`

注册配置重载回调函数。

**参数:**
- `callback`: 回调函数

**返回:**
- 无

### AppConfig

应用程序配置数据模型。

#### 属性

- `qbittorrent`: `QBittorrentConfig` - qBittorrent客户端配置
- `deepseek`: `DeepSeekConfig` - DeepSeek AI配置
- `categories`: `Dict[str, CategoryConfig]` - 分类配置
- `path_mapping`: `Dict[str, str]` - 全局路径映射
- `use_nas_paths_directly`: `bool` - 是否直接使用NAS路径
- `check_interval`: `float` - 监控间隔（秒）
- `max_retries`: `int` - 最大重试次数
- `retry_delay`: `float` - 重试延迟（秒）
- `notifications`: `NotificationConfig` - 通知配置
- `hot_reload`: `bool` - 是否启用热重载
- `log_level`: `str` - 日志级别
- `log_file`: `Optional[str]` - 日志文件路径

### CategoryConfig

分类配置数据模型。

#### 属性

- `save_path`: `str` - 保存路径
- `keywords`: `List[str]` - 关键词列表
- `description`: `str` - 分类描述
- `foreign_keywords`: `Optional[List[str]]` - 外语关键词
- `rules`: `Optional[List[Dict[str, Any]]]` - 增强规则
- `priority`: `int` - 分类优先级

## qBittorrent 客户端 API

### QBittorrentClient

qBittorrent客户端API封装。

#### 类方法

##### `__init__(self, config: QBittorrentConfig, app_config: Optional[AppConfig] = None)`

初始化qBittorrent客户端。

**参数:**
- `config`: qBittorrent配置
- `app_config`: 应用程序配置，可选

**返回:**
- 无

##### `async def __aenter__(self)`

异步上下文管理器入口。

**参数:**
- 无

**返回:**
- `QBittorrentClient`: 客户端实例

##### `async def __aexit__(self, exc_type, exc, tb)`

异步上下文管理器出口。

**参数:**
- `exc_type`: 异常类型
- `exc`: 异常实例
- `tb`: 追溯对象

**返回:**
- 无

##### `async def login(self)`

登录qBittorrent。

**参数:**
- 无

**返回:**
- 无

**异常:**
- `QbtAuthError`: 认证失败
- `QbtRateLimitError`: API限速
- `NetworkError`: 网络错误

##### `async def get_version(self) -> str`

获取qBittorrent版本信息。

**参数:**
- 无

**返回:**
- `str`: 版本信息

**异常:**
- `QBittorrentError`: 获取版本失败
- `NetworkError`: 网络错误

##### `async def get_existing_categories(self) -> Dict[str, Dict[str, Any]]`

获取现有的分类及其详细信息。

**参数:**
- 无

**返回:**
- `Dict[str, Dict[str, Any]]`: 分类信息字典

**异常:**
- `QbtPermissionError`: 权限不足
- `QBittorrentError`: 获取分类失败
- `NetworkError`: 网络错误

##### `async def ensure_categories(self, categories: Dict[str, CategoryConfig])`

确保所有分类存在，动态更新分类路径。

**参数:**
- `categories`: 分类配置字典

**返回:**
- 无

##### `async def add_torrent(self, magnet_link: str, category: str, **kwargs) -> bool`

添加磁力链接。

**参数:**
- `magnet_link`: 磁力链接
- `category`: 分类名称
- `**kwargs`: 额外参数，如paused（是否暂停）

**返回:**
- `bool`: 是否添加成功

**异常:**
- `TorrentParseError`: 磁力链接解析失败
- `QbtPermissionError`: 权限不足
- `QbtRateLimitError`: API限速
- `NetworkError`: 网络错误

##### `async def _is_duplicate(self, torrent_hash: str) -> bool`

检查种子是否已存在。

**参数:**
- `torrent_hash`: 种子哈希值

**返回:**
- `bool`: 是否重复

##### `async def get_torrents(self, category: Optional[str] = None) -> List[Dict[str, Any]]`

获取种子列表。

**参数:**
- `category`: 分类名称，可选

**返回:**
- `List[Dict[str, Any]]`: 种子信息列表

**异常:**
- `QBittorrentError`: 获取种子列表失败
- `NetworkError`: 网络错误

##### `async def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool`

删除种子。

**参数:**
- `torrent_hash`: 种子哈希值
- `delete_files`: 是否删除文件

**返回:**
- `bool`: 是否删除成功

**异常:**
- `QBittorrentError`: 删除种子失败
- `NetworkError`: 网络错误

##### `async def pause_torrent(self, torrent_hash: str) -> bool`

暂停种子。

**参数:**
- `torrent_hash`: 种子哈希值

**返回:**
- `bool`: 是否暂停成功

**异常:**
- `QBittorrentError`: 暂停种子失败
- `NetworkError`: 网络错误

##### `async def resume_torrent(self, torrent_hash: str) -> bool`

恢复种子。

**参数:**
- `torrent_hash`: 种子哈希值

**返回:**
- `bool`: 是否恢复成功

**异常:**
- `QBittorrentError`: 恢复种子失败
- `NetworkError`: 网络错误

##### `async def get_torrent_properties(self, torrent_hash: str) -> Dict[str, Any]`

获取种子属性。

**参数:**
- `torrent_hash`: 种子哈希值

**返回:**
- `Dict[str, Any]`: 种子属性字典

**异常:**
- `QBittorrentError`: 获取种子属性失败
- `NetworkError`: 网络错误

##### `async def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]`

获取种子文件列表。

**参数:**
- `torrent_hash`: 种子哈希值

**返回:**
- `List[Dict[str, Any]]`: 文件信息列表

**异常:**
- `QBittorrentError`: 获取种子文件失败
- `NetworkError`: 网络错误

## AI 分类器 API

### AIClassifier

AI分类器基类，提供种子智能分类功能。

#### 类方法

##### `__init__(self, config: DeepSeekConfig)`

初始化AI分类器。

**参数:**
- `config`: DeepSeek配置

**返回:**
- 无

##### `async def classify(self, torrent_name: Optional[str], categories: Dict[str, CategoryConfig]) -> str`

分类种子名称。

**参数:**
- `torrent_name`: 种子名称
- `categories`: 分类配置字典

**返回:**
- `str`: 分类名称

### DeepSeekClassifier

DeepSeek AI分类器实现。

#### 类方法

##### `async def _classify_with_retry(self, torrent_name: str, categories: Dict[str, CategoryConfig]) -> str`

带重试机制的分类方法。

**参数:**
- `torrent_name`: 种子名称
- `categories`: 分类配置字典

**返回:**
- `str`: 分类名称

**异常:**
- `AIApiError`: API调用错误
- `AICreditError`: API额度不足
- `AIRateLimitError`: API限速

##### `def _build_prompt(self, torrent_name: str, categories: Dict[str, CategoryConfig]) -> str`

构建AI提示词。

**参数:**
- `torrent_name`: 种子名称
- `categories`: 分类配置字典

**返回:**
- `str`: 提示词

##### `def _rule_based_classify(self, torrent_name: Optional[str], categories: Dict[str, CategoryConfig]) -> str`

规则引擎分类。

**参数:**
- `torrent_name`: 种子名称
- `categories`: 分类配置字典

**返回:**
- `str`: 分类名称

### AIClassifierFactory

AI分类器工厂类。

#### 静态方法

##### `def create_classifier(provider: str, config: DeepSeekConfig) -> BaseAIClassifier`

根据提供商创建对应的分类器。

**参数:**
- `provider`: AI提供商名称（如"deepseek"）
- `config`: DeepSeek配置

**返回:**
- `BaseAIClassifier`: AI分类器实例

**异常:**
- `ValueError`: 不支持的AI提供商

## 剪贴板监控器 API

### ClipboardMonitor

剪贴板监控器，负责监控剪贴板内容并处理磁力链接和URL。

#### 类方法

##### `__init__(self, qbt: QBittorrentClient, config: AppConfig)`

初始化剪贴板监控器。

**参数:**
- `qbt`: qBittorrent客户端实例
- `config`: 应用程序配置

**返回:**
- 无

##### `async def start(self)`

启动剪贴板监控。

**参数:**
- 无

**返回:**
- 无

##### `def stop(self)`

停止剪贴板监控。

**参数:**
- 无

**返回:**
- 无

##### `async def _monitor_cycle(self)`

监控循环。

**参数:**
- 无

**返回:**
- 无

##### `async def _process_magnet(self, magnet_link: str)`

处理磁力链接。

**参数:**
- `magnet_link`: 磁力链接

**返回:**
- 无

##### `async def _process_url(self, url: str)`

处理网页URL。

**参数:**
- `url`: 网页URL

**返回:**
- 无

##### `async def _check_duplicate(self, record: TorrentRecord) -> bool`

检查种子是否重复。

**参数:**
- `record`: 种子记录

**返回:**
- `bool`: 是否重复

##### `async def _classify_torrent(self, record: TorrentRecord) -> str`

分类种子。

**参数:**
- `record`: 种子记录

**返回:**
- `str`: 分类名称

##### `async def _get_save_path(self, category: str) -> str`

获取分类的保存路径。

**参数:**
- `category`: 分类名称

**返回:**
- `str`: 保存路径

##### `async def _add_torrent_to_client(self, record: TorrentRecord) -> bool`

将种子添加到qBittorrent客户端。

**参数:**
- `record`: 种子记录

**返回:**
- `bool`: 是否添加成功

##### `def get_status(self) -> Dict`

获取监控状态。

**参数:**
- 无

**返回:**
- `Dict`: 状态信息字典

##### `def get_history(self, limit: int = 100) -> List[Dict]`

获取处理历史记录。

**参数:**
- `limit`: 历史记录数量限制

**返回:**
- `List[Dict]`: 历史记录列表

##### `def clear_history(self)`

清空历史记录。

**参数:**
- 无

**返回:**
- 无

##### `def reset_stats(self)`

重置统计信息。

**参数:**
- 无

**返回:**
- 无

### TorrentRecord

种子处理记录数据类。

#### 属性

- `magnet_link`: `str` - 磁力链接
- `torrent_hash`: `str` - 种子哈希值
- `torrent_name`: `str` - 种子名称
- `category`: `str` - 分类名称
- `save_path`: `str` - 保存路径
- `status`: `str` - 状态
- `timestamp`: `datetime` - 时间戳
- `error_message`: `str` - 错误消息
- `classification_method`: `str` - 分类方法

## 网页爬虫 API

### WebCrawler

网页爬虫，负责抓取网站种子信息。

#### 类方法

##### `__init__(self, config: AppConfig, qbt_client: QBittorrentClient)`

初始化网页爬虫。

**参数:**
- `config`: 应用程序配置
- `qbt_client`: qBittorrent客户端实例

**返回:**
- 无

##### `async def crawl_xxxclub_search(self, search_url: str, max_pages: int = 1) -> List[TorrentInfo]`

抓取XXXClub搜索页面。

**参数:**
- `search_url`: 搜索页面URL
- `max_pages`: 最大抓取页数

**返回:**
- `List[TorrentInfo]`: 种子信息列表

**异常:**
- `CrawlerError`: 爬虫错误

##### `async def extract_magnet_links(self, torrents: List[TorrentInfo]) -> List[TorrentInfo]`

从种子详情页面提取磁力链接。

**参数:**
- `torrents`: 种子信息列表

**返回:**
- `List[TorrentInfo]`: 更新后的种子信息列表

##### `async def add_torrents_to_qbittorrent(self, torrents: List[TorrentInfo]) -> List[TorrentInfo]`

将种子批量添加到qBittorrent。

**参数:**
- `torrents`: 种子信息列表

**返回:**
- `List[TorrentInfo]`: 更新后的种子信息列表

##### `def get_stats(self) -> Dict[str, Any]`

获取爬虫统计信息。

**参数:**
- 无

**返回:**
- `Dict[str, Any]`: 统计信息字典

##### `def reset_stats(self)`

重置统计信息。

**参数:**
- 无

**返回:**
- 无

### TorrentInfo

种子信息数据类。

#### 属性

- `title`: `str` - 种子标题
- `detail_url`: `str` - 详情页面URL
- `magnet_link`: `str` - 磁力链接
- `size`: `str` - 文件大小
- `seeders`: `int` - 种子数
- `leechers`: `int` - 下载数
- `category`: `str` - 分类
- `status`: `str` - 状态

### crawl_and_add_torrents

便捷函数：抓取并添加种子。

#### 函数签名

```python
async def crawl_and_add_torrents(
    search_url: str, 
    config: AppConfig, 
    qbt_client: QBittorrentClient, 
    max_pages: int = 1
) -> Dict[str, Any]
```

#### 参数

- `search_url`: 搜索页面URL
- `config`: 应用配置
- `qbt_client`: qBittorrent客户端
- `max_pages`: 最大抓取页数

#### 返回

- `Dict[str, Any]`: 处理结果统计

## 工具函数 API

### parse_magnet

解析磁力链接。

#### 函数签名

```python
def parse_magnet(magnet_link: str) -> Tuple[Optional[str], Optional[str]]
```

#### 参数

- `magnet_link`: 磁力链接字符串

#### 返回

- `Tuple[Optional[str], Optional[str]]`: (哈希值, 名称) 元组

### validate_magnet_link

验证磁力链接格式是否正确。

#### 函数签名

```python
def validate_magnet_link(magnet_link: str) -> bool
```

#### 参数

- `magnet_link`: 磁力链接字符串

#### 返回

- `bool`: 是否有效

### format_size

格式化文件大小显示。

#### 函数签名

```python
def format_size(size_bytes: int) -> str
```

#### 参数

- `size_bytes`: 文件大小（字节）

#### 返回

- `str`: 格式化后的大小字符串

### sanitize_filename

清理文件名，移除不安全字符。

#### 函数签名

```python
def sanitize_filename(filename: str) -> str
```

#### 参数

- `filename`: 原始文件名

#### 返回

- `str`: 清理后的文件名

### is_episode_content

判断是否为剧集内容。

#### 函数签名

```python
def is_episode_content(filename: str) -> bool
```

#### 参数

- `filename`: 文件名

#### 返回

- `bool`: 是否为剧集内容

### is_movie_content

判断是否为电影内容。

#### 函数签名

```python
def is_movie_content(filename: str) -> bool
```

#### 参数

- `filename`: 文件名

#### 返回

- `bool`: 是否为电影内容

### extract_file_extensions

从文件列表中提取文件扩展名统计。

#### 函数签名

```python
def extract_file_extensions(file_list: List[Dict[str, Any]]) -> Dict[str, int]
```

#### 参数

- `file_list`: 文件信息列表

#### 返回

- `Dict[str, int]`: 扩展名统计字典

### analyze_torrent_content

分析种子内容特征。

#### 函数签名

```python
def analyze_torrent_content(file_list: List[Dict[str, Any]]) -> Dict[str, Any]
```

#### 参数

- `file_list`: 文件信息列表

#### 返回

- `Dict[str, Any]`: 内容分析结果

### setup_logging

配置日志系统。

#### 函数签名

```python
def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger
```

#### 参数

- `level`: 日志级别
- `log_file`: 日志文件路径，可选

#### 返回

- `logging.Logger`: 日志记录器

## 通知系统 API

### NotificationManager

通知管理器，负责发送各种通知。

#### 类方法

##### `__init__(self, config: Dict[str, Any])`

初始化通知管理器。

**参数:**
- `config`: 通知配置字典

**返回:**
- 无

##### `async def send_torrent_success(self, torrent_name: str, category: str, save_path: str, torrent_hash: str, classification_method: str = "AI")`

发送种子添加成功通知。

**参数:**
- `torrent_name`: 种子名称
- `category`: 分类名称
- `save_path`: 保存路径
- `torrent_hash`: 种子哈希值
- `classification_method`: 分类方法

**返回:**
- 无

##### `async def send_torrent_failure(self, torrent_name: str, error_message: str, torrent_hash: str, attempted_category: str = "")`

发送种子添加失败通知。

**参数:**
- `torrent_name`: 种子名称
- `error_message`: 错误消息
- `torrent_hash`: 种子哈希值
- `attempted_category`: 尝试的分类

**返回:**
- 无

##### `async def send_duplicate_notification(self, torrent_name: str, torrent_hash: str)`

发送重复种子通知。

**参数:**
- `torrent_name`: 种子名称
- `torrent_hash`: 种子哈希值

**返回:**
- 无

##### `async def send_statistics(self, stats: Dict[str, int])`

发送统计信息。

**参数:**
- `stats`: 统计信息字典

**返回:**
- 无

## 异常类型

### QBittorrentMonitorError

项目基础异常类。

#### 属性

- `details`: 异常详细信息
- `retry_after`: 重试时间（秒）

### ConfigError

配置相关异常。

### QBittorrentError

qBittorrent操作异常基类。

### NetworkError

网络通信异常。

### QbtAuthError

qBittorrent认证异常。

### QbtRateLimitError

qBittorrent API限速异常。

### QbtPermissionError

qBittorrent权限异常。

### AIError

AI相关异常基类。

### AIApiError

AI API调用异常。

### AICreditError

AI额度不足异常。

### AIRateLimitError

AI API限速异常。

### ClassificationError

分类相关异常。

### ClipboardError

剪贴板访问异常。

### TorrentParseError

种子解析异常。

### NotificationError

通知发送异常。

### CrawlerError

网页爬虫异常。

### ParseError

网页解析异常。

## 使用示例

### 基本使用

```python
import asyncio
from qbittorrent_monitor.config import ConfigManager
from qbittorrent_monitor.qbittorrent_client import QBittorrentClient
from qbittorrent_monitor.clipboard_monitor import ClipboardMonitor

async def main():
    # 加载配置
    config_manager = ConfigManager()
    config = await config_manager.load_config()
    
    # 创建qBittorrent客户端
    async with QBittorrentClient(config.qbittorrent, config) as qbt:
        # 创建剪贴板监控器
        monitor = ClipboardMonitor(qbt, config)
        
        # 启动监控
        await monitor.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### 添加种子

```python
import asyncio
from qbittorrent_monitor.config import ConfigManager
from qbittorrent_monitor.qbittorrent_client import QBittorrentClient

async def main():
    # 加载配置
    config_manager = ConfigManager()
    config = await config_manager.load_config()
    
    # 创建qBittorrent客户端
    async with QBittorrentClient(config.qbittorrent, config) as qbt:
        # 添加种子
        magnet_link = "magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10&dn=Sintel"
        success = await qbt.add_torrent(magnet_link, "movies")
        
        if success:
            print("种子添加成功")
        else:
            print("种子添加失败")

if __name__ == "__main__":
    asyncio.run(main())
```

### 网页爬虫

```python
import asyncio
from qbittorrent_monitor.config import ConfigManager
from qbittorrent_monitor.qbittorrent_client import QBittorrentClient
from qbittorrent_monitor.web_crawler import crawl_and_add_torrents

async def main():
    # 加载配置
    config_manager = ConfigManager()
    config = await config_manager.load_config()
    
    # 创建qBittorrent客户端
    async with QBittorrentClient(config.qbittorrent, config) as qbt:
        # 抓取并添加种子
        search_url = "https://www.xxxclub.to/torrents/search/test"
        result = await crawl_and_add_torrents(search_url, config, qbt, max_pages=1)
        
        if result['success']:
            print(f"处理完成: {result['message']}")
        else:
            print(f"处理失败: {result['message']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### AI分类

```python
import asyncio
from qbittorrent_monitor.config import ConfigManager
from qbittorrent_monitor.ai_classifier import AIClassifierFactory
from qbittorrent_monitor.config import DeepSeekConfig, CategoryConfig

async def main():
    # 创建AI配置
    deepseek_config = DeepSeekConfig(
        api_key="your_api_key",
        model="deepseek-chat",
        base_url="https://api.deepseek.com"
    )
    
    # 创建分类配置
    categories = {
        "tv": CategoryConfig(
            savePath="/downloads/tv/",
            keywords=["tv", "show"],
            description="电视节目"
        ),
        "movies": CategoryConfig(
            savePath="/downloads/movies/",
            keywords=["movie", "film"],
            description="电影"
        )
    }
    
    # 创建AI分类器
    classifier = AIClassifierFactory.create_classifier("deepseek", deepseek_config)
    
    # 分类种子
    torrent_name = "TV.Show.S01E01.1080p.BluRay"
    category = await classifier.classify(torrent_name, categories)
    
    print(f"分类结果: {category}")

if __name__ == "__main__":
    asyncio.run(main())