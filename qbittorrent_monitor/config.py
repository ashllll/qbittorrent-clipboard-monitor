from __future__ import annotations

"""
增强的配置管理模块

支持：
- 多种配置格式（JSON, YAML, TOML）
- 环境变量覆盖
- 配置热加载
- 配置验证
"""

import json
import os
import logging
import threading
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pydantic import BaseModel, ValidationError, Field, field_validator, ConfigDict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import asyncio
from collections import defaultdict


@dataclass
class ConfigStats:
    """配置管理统计信息"""
    load_count: int = 0
    reload_count: int = 0
    validation_errors: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    last_load_time: Optional[datetime] = None
    last_reload_time: Optional[datetime] = None
    average_load_time: float = 0.0
    load_times: List[float] = field(default_factory=list)
    
    def record_load_time(self, load_time: float):
        """记录加载时间"""
        self.load_times.append(load_time)
        if len(self.load_times) > 100:  # 只保留最近100次记录
            self.load_times.pop(0)
        self.average_load_time = sum(self.load_times) / len(self.load_times)
    
    def get_cache_hit_rate(self) -> float:
        """获取缓存命中率"""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0


@dataclass
class ConfigCacheEntry:
    """配置缓存条目"""
    data: Any
    hash_value: str
    timestamp: datetime
    access_count: int = 0
    last_access: Optional[datetime] = None
    
    def is_expired(self, ttl_seconds: int = 300) -> bool:
        """检查缓存是否过期（默认5分钟）"""
        return (datetime.now() - self.timestamp).total_seconds() > ttl_seconds
    
    def touch(self):
        """更新访问时间和计数"""
        self.access_count += 1
        self.last_access = datetime.now()


class ConfigCache:
    """线程安全的配置缓存"""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._entries: Dict[str, ConfigCacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional["AppConfig"]:
        """获取缓存数据"""
        with self._lock:
            entry = self._entries.get(key)
            if not entry:
                return None
            if entry.is_expired(self.ttl_seconds):
                del self._entries[key]
                return None
            entry.touch()
            return entry.data  # type: ignore[return-value]

    def set(self, key: str, value: "AppConfig"):
        """设置缓存数据"""
        with self._lock:
            self._entries[key] = ConfigCacheEntry(
                data=value,
                hash_value=key,
                timestamp=datetime.now(),
            )

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._entries.clear()


class ConfigTemplate:
    """配置模板系统"""
    
    @staticmethod
    def get_development_template() -> Dict[str, Any]:
        """开发环境配置模板"""
        return {
            "log_level": "DEBUG",
            "hot_reload": True,
            "qbittorrent": {
                "host": "localhost",
                "port": 8080,
                "verify_ssl": False
            },
            "web_crawler": {
                "max_retries": 1,
                "page_timeout": 30000,
                "max_concurrent_extractions": 1
            }
        }
    
    @staticmethod
    def get_production_template() -> Dict[str, Any]:
        """生产环境配置模板"""
        return {
            "log_level": "INFO",
            "hot_reload": False,
            "qbittorrent": {
                "verify_ssl": True,
                "use_https": True
            },
            "web_crawler": {
                "max_retries": 5,
                "page_timeout": 60000,
                "max_concurrent_extractions": 5
            },
            "notifications": {
                "enabled": True
            }
        }
    
    @staticmethod
    def get_testing_template() -> Dict[str, Any]:
        """测试环境配置模板"""
        return {
            "log_level": "WARNING",
            "hot_reload": False,
            "check_interval": 0.1,
            "web_crawler": {
                "enabled": False
            },
            "notifications": {
                "enabled": False
            }
        }


class CategoryConfig(BaseModel):
    """分类配置数据模型"""
    save_path: str = Field(alias='savePath')
    keywords: List[str] = []
    description: str = ""
    foreign_keywords: Optional[List[str]] = Field(default=None, alias='foreign_keywords')
    # 增强规则配置
    rules: Optional[List[Dict[str, Any]]] = None
    priority: int = 0  # 分类优先级
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator('save_path')
    @classmethod
    def validate_save_path(cls, v: str) -> str:
        """验证保存路径"""
        if not v or not v.strip():
            raise ValueError('保存路径不能为空')
        # 确保路径以/结尾
        if not v.endswith('/'):
            v = v + '/'
        return v
    
    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v: int) -> int:
        """验证优先级"""
        if v < 0 or v > 100:
            raise ValueError('优先级必须在0-100之间')
        return v
    
    @field_validator('keywords')
    @classmethod
    def validate_keywords(cls, v: List[str]) -> List[str]:
        """验证关键词"""
        if v:
            # 去除空字符串和重复项
            v = list(set(k.strip() for k in v if k.strip()))
        return v


class PathMappingRule(BaseModel):
    """路径映射规则"""
    source_prefix: str
    target_prefix: str
    description: Optional[str] = None


class QBittorrentConfig(BaseModel):
    """qBittorrent配置数据模型"""
    host: str = "192.168.1.40"
    port: int = 8989
    username: str = "admin"
    password: str = "password"
    use_https: bool = False
    verify_ssl: bool = True
    # 移到这里的路径配置
    use_nas_paths_directly: bool = False
    path_mapping: List[PathMappingRule] = []
    
    @field_validator('host')
    @classmethod
    def validate_host(cls, v: str) -> str:
        """验证主机地址"""
        if not v or not v.strip():
            raise ValueError('主机地址不能为空')
        return v.strip()
    
    @field_validator('port')
    @classmethod
    def validate_port(cls, v: int) -> int:
        """验证端口号"""
        if not (1 <= v <= 65535):
            raise ValueError('端口号必须在1-65535之间')
        return v
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """验证用户名"""
        if not v or not v.strip():
            raise ValueError('用户名不能为空')
        return v.strip()
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """验证密码"""
        if not v:
            raise ValueError('密码不能为空')
        return v


class DeepSeekConfig(BaseModel):
    """DeepSeek AI配置数据模型"""
    api_key: str = ""
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    # Few-shot示例
    few_shot_examples: Optional[List[Dict[str, str]]] = None
    prompt_template: str = """你是下载分类助手。根据给定类别快速判断种子所属类别，并只返回 tv/movies/adult/anime/music/games/software/other 中的一个。

种子: {torrent_name}
分类列表:
{category_descriptions}

常见关键词:
{category_keywords}

{few_shot_examples}
若无法确定，返回 other。"""
    
    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """验证API基础URL"""
        if not v or not v.strip():
            raise ValueError('API基础URL不能为空')
        if not v.startswith(('http://', 'https://')):
            raise ValueError('API基础URL必须以http://或https://开头')
        return v.strip().rstrip('/')
    
    @field_validator('timeout')
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """验证超时时间"""
        if v <= 0 or v > 300:
            raise ValueError('超时时间必须在1-300秒之间')
        return v
    
    @field_validator('max_retries')
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        """验证最大重试次数"""
        if v < 0 or v > 10:
            raise ValueError('最大重试次数必须在0-10之间')
        return v
    
    @field_validator('retry_delay')
    @classmethod
    def validate_retry_delay(cls, v: float) -> float:
        """验证重试延迟"""
        if v < 0 or v > 60:
            raise ValueError('重试延迟必须在0-60秒之间')
        return v


class ConsoleNotificationConfig(BaseModel):
    """控制台通知配置"""
    enabled: bool = True
    colored: bool = True
    show_details: bool = True
    show_statistics: bool = True


class WebCrawlerConfig(BaseModel):
    """网页爬虫配置"""
    enabled: bool = True
    # 性能参数
    page_timeout: int = 60000  # 页面超时时间(毫秒)
    wait_for: int = 3  # 页面加载等待时间(秒)
    delay_before_return: int = 2  # 返回前等待时间(秒)
    # 重试配置
    max_retries: int = 3  # 最大重试次数
    base_delay: int = 5  # 基础延迟时间(秒)
    max_delay: int = 60  # 最大延迟时间(秒)
    # 并发配置
    max_concurrent_extractions: int = 3  # 最大并发提取数
    inter_request_delay: float = 1.5  # 请求间延迟(秒)
    # AI分类配置
    ai_classify_torrents: bool = True
    add_torrents_paused: bool = False
    # 代理配置
    proxy: Optional[str] = None
    
    @field_validator('page_timeout')
    @classmethod
    def validate_page_timeout(cls, v: int) -> int:
        """验证页面超时时间"""
        if v <= 0 or v > 300000:  # 最大5分钟
            raise ValueError('页面超时时间必须在1-300000毫秒之间')
        return v
    
    @field_validator('wait_for')
    @classmethod
    def validate_wait_for(cls, v: int) -> int:
        """验证页面加载等待时间"""
        if v < 0 or v > 60:
            raise ValueError('页面加载等待时间必须在0-60秒之间')
        return v
    
    @field_validator('delay_before_return')
    @classmethod
    def validate_delay_before_return(cls, v: int) -> int:
        """验证返回前等待时间"""
        if v < 0 or v > 30:
            raise ValueError('返回前等待时间必须在0-30秒之间')
        return v
    
    @field_validator('max_retries')
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        """验证最大重试次数"""
        if v < 0 or v > 10:
            raise ValueError('最大重试次数必须在0-10之间')
        return v
    
    @field_validator('base_delay')
    @classmethod
    def validate_base_delay(cls, v: int) -> int:
        """验证基础延迟时间"""
        if v < 0 or v > 300:
            raise ValueError('基础延迟时间必须在0-300秒之间')
        return v
    
    @field_validator('max_delay')
    @classmethod
    def validate_max_delay(cls, v: int) -> int:
        """验证最大延迟时间"""
        if v < 0 or v > 600:
            raise ValueError('最大延迟时间必须在0-600秒之间')
        return v
    
    @field_validator('max_concurrent_extractions')
    @classmethod
    def validate_max_concurrent_extractions(cls, v: int) -> int:
        """验证最大并发提取数"""
        if v <= 0 or v > 20:
            raise ValueError('最大并发提取数必须在1-20之间')
        return v
    
    @field_validator('inter_request_delay')
    @classmethod
    def validate_inter_request_delay(cls, v: float) -> float:
        """验证请求间延迟"""
        if v < 0 or v > 60:
            raise ValueError('请求间延迟必须在0-60秒之间')
        return v
    
    @field_validator('proxy')
    @classmethod
    def validate_proxy(cls, v: Optional[str]) -> Optional[str]:
        """验证代理配置"""
        if v and not v.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
            raise ValueError('代理地址格式不正确，必须以http://、https://、socks4://或socks5://开头')
        return v


class NotificationConfig(BaseModel):
    """通知配置"""
    enabled: bool = False
    console: ConsoleNotificationConfig = ConsoleNotificationConfig()
    services: List[str] = []  # telegram, discord, email等
    webhook_url: Optional[str] = None
    api_token: Optional[str] = None
    chat_id: Optional[str] = None
    email_config: Optional[Dict[str, Any]] = None


class AppConfig(BaseModel):
    """应用配置数据模型"""
    qbittorrent: QBittorrentConfig
    deepseek: DeepSeekConfig
    categories: Dict[str, CategoryConfig]
    # 全局路径映射（向后兼容）
    path_mapping: Dict[str, str] = {}
    use_nas_paths_directly: bool = False
    # 监控配置
    check_interval: float = 2.0
    max_retries: int = 3
    retry_delay: float = 5.0
    # 网页爬虫配置
    web_crawler: WebCrawlerConfig = WebCrawlerConfig()
    # 通知配置
    notifications: NotificationConfig = NotificationConfig()
    # 热加载配置
    hot_reload: bool = True
    # 日志配置
    log_level: str = "INFO"
    log_file: Optional[str] = "magnet_monitor.log"
    # 添加缺失的配置属性
    add_torrents_paused: bool = False
    ai_classify_torrents: bool = True
    proxy: Optional[str] = None


class ConfigFileHandler(FileSystemEventHandler):
    """配置文件变化监控处理器"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.logger = logging.getLogger('Config.FileHandler')
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        if event.src_path == str(self.config_manager.config_path):
            self.logger.info(f"配置文件已修改: {event.src_path}")
            # 使用线程安全的方式触发重载
            threading.Thread(
                target=self._trigger_reload,
                daemon=True
            ).start()
    
    def _trigger_reload(self):
        """在新线程中触发配置重载"""
        try:
            # 尝试获取运行中的事件循环
            loop = asyncio.get_running_loop()
            # 线程安全地调度协程
            asyncio.run_coroutine_threadsafe(
                self.config_manager.reload_config(), 
                loop
            )
        except RuntimeError:
            # 如果没有运行中的事件循环，创建新的
            try:
                asyncio.run(self.config_manager.reload_config())
            except Exception as e:
                self.logger.error(f"配置重载失败: {str(e)}")


class ConfigManager:
    """增强的配置管理器"""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        self.logger = logging.getLogger('ConfigManager')
        
        if config_path is None:
            # 使用脚本同目录下的配置文件
            self.config_path = Path(__file__).parent / 'config.json'
        else:
            self.config_path = Path(config_path)
            
        self.config: Optional[AppConfig] = None
        self.observer: Optional[Observer] = None
        self._reload_callbacks: List[callable] = []
        
        # 增强功能
        self._stats = ConfigStats()
        self.cache_ttl = 300  # 缓存TTL（秒）
        self._cache = ConfigCache(ttl_seconds=self.cache_ttl)
        self._validation_cache: Dict[str, bool] = {}
        self._template_cache: Dict[str, Dict[str, Any]] = {}
        
        # 配置选项
        self.enable_validation_cache = True
        self.enable_performance_monitoring = True
    
    async def load_config(self) -> AppConfig:
        """增强的配置加载方法"""
        start_time = time.time()
        
        try:
            # 检查缓存
            if self.enable_performance_monitoring:
                cache_key = self._get_cache_key()
                cached_config = self._get_from_cache(cache_key)
                if cached_config:
                    self._stats.cache_hits += 1
                    self.config = cached_config
                    return self.config
                else:
                    self._stats.cache_misses += 1
            
            # 创建默认配置（如果不存在）
            if not self.config_path.exists():
                self._create_default_config()
            
            # 加载配置数据
            config_data = self._load_config_file()
            config_data = self._apply_env_overrides(config_data)
            
            # 验证配置
            if self.enable_validation_cache:
                validation_key = self._get_validation_key(config_data)
                if validation_key not in self._validation_cache:
                    self._validate_config_data(config_data)
                    self._validation_cache[validation_key] = True
            
            # 创建配置对象
            self.config = AppConfig(**config_data)
            
            # 缓存配置
            if self.enable_performance_monitoring:
                self._put_to_cache(cache_key, self.config)
            
            # 启动热加载监控
            if self.config.hot_reload:
                self._start_file_watcher()
            
            # 记录统计信息
            load_time = time.time() - start_time
            self._stats.load_count += 1
            self._stats.last_load_time = datetime.now()
            self._stats.record_load_time(load_time)
            
            self.logger.info(f"配置加载成功: {self.config_path} (耗时: {load_time:.3f}s)")
            return self.config
            
        except ValidationError as e:
            self._stats.validation_errors += 1
            from .exceptions import ConfigError
            raise ConfigError(f"配置验证失败: {str(e)}") from e
        except Exception as e:
            from .exceptions import ConfigError
            raise ConfigError(f"配置加载失败: {str(e)}") from e
    
    def _load_config_file(self) -> Dict[str, Any]:
        """根据文件扩展名加载不同格式的配置文件"""
        suffix = self.config_path.suffix.lower()
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if suffix == '.json':
                    return json.load(f)
                elif suffix in ['.yaml', '.yml']:
                    import yaml
                    return yaml.safe_load(f)
                elif suffix == '.toml':
                    import tomllib
                    return tomllib.load(f)
                else:
                    # 默认尝试JSON
                    return json.load(f)
        except Exception as e:
            raise ValueError(f"配置文件格式错误: {str(e)}") from e
    
    def _apply_env_overrides(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """应用环境变量覆盖"""
        # qBittorrent配置覆盖
        qbt_config = config_data.get('qbittorrent', {})
        qbt_config.update({
            'host': os.getenv('QBIT_HOST', qbt_config.get('host', 'localhost')),
            'port': int(os.getenv('QBIT_PORT', qbt_config.get('port', 8080))),
            'username': os.getenv('QBIT_USER', qbt_config.get('username', 'admin')),
            'password': os.getenv('QBIT_PASS', qbt_config.get('password', 'password'))
        })
        config_data['qbittorrent'] = qbt_config
        
        # DeepSeek配置覆盖
        deepseek_config = config_data.get('deepseek', {})
        deepseek_config.update({
            'api_key': os.getenv('DEEPSEEK_API_KEY', deepseek_config.get('api_key', '')),
            'base_url': os.getenv('DEEPSEEK_BASE_URL', deepseek_config.get('base_url', 'https://api.deepseek.com'))
        })
        config_data['deepseek'] = deepseek_config
        
        return config_data
    
    def _start_file_watcher(self):
        """启动配置文件监控"""
        if self.observer is not None:
            return
            
        self.observer = Observer()
        event_handler = ConfigFileHandler(self)
        self.observer.schedule(
            event_handler,
            str(self.config_path.parent),
            recursive=False
        )
        self.observer.start()
        self.logger.info("配置文件热加载监控已启动")
    
    def _get_cache_key(self) -> str:
        """生成配置缓存键"""
        try:
            # 基于文件修改时间和路径生成缓存键
            stat = self.config_path.stat()
            content = f"{self.config_path}:{stat.st_mtime}:{stat.st_size}"
            return hashlib.md5(content.encode()).hexdigest()
        except Exception:
            return f"fallback:{time.time()}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[AppConfig]:
        """从缓存获取配置"""
        return self._cache.get(cache_key)
    
    def _put_to_cache(self, cache_key: str, config: AppConfig):
        """将配置放入缓存"""
        self._cache.set(cache_key, config)
    
    def _get_validation_key(self, config_data: Dict[str, Any]) -> str:
        """生成配置验证键"""
        content = json.dumps(config_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(content.encode()).hexdigest()
    
    def _validate_config_data(self, config_data: Dict[str, Any]):
        """验证配置数据"""
        # 基本结构验证
        required_sections = ['qbittorrent', 'deepseek', 'categories']
        for section in required_sections:
            if section not in config_data:
                raise ValueError(f"缺少必需的配置节: {section}")
        
        # 分类配置验证
        categories = config_data.get('categories', {})
        if not categories:
            raise ValueError("至少需要配置一个分类")
        
        # 验证保存路径不重复
        save_paths = []
        for name, category in categories.items():
            save_path = category.get('savePath') or category.get('save_path')
            if save_path in save_paths:
                raise ValueError(f"分类 {name} 的保存路径与其他分类重复: {save_path}")
            save_paths.append(save_path)
    
    async def reload_config(self):
        """增强的配置重载方法"""
        start_time = time.time()
        
        try:
            old_config = self.config
            
            # 清理缓存以强制重新加载
            self._cache.clear()
            self._validation_cache.clear()
            
            new_config = await self.load_config()
            
            # 通知所有注册的回调函数
            for callback in self._reload_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(old_config, new_config)
                    else:
                        callback(old_config, new_config)
                except Exception as e:
                    self.logger.error(f"配置重载回调执行失败: {str(e)}")
            
            # 记录统计信息
            reload_time = time.time() - start_time
            self._stats.reload_count += 1
            self._stats.last_reload_time = datetime.now()
            
            self.logger.info(f"配置重载完成 (耗时: {reload_time:.3f}s)")
            
        except Exception as e:
            self.logger.error(f"配置重载失败: {str(e)}")
    
    def register_reload_callback(self, callback: callable):
        """注册配置重载回调函数"""
        self._reload_callbacks.append(callback)
    
    def stop_file_watcher(self):
        """停止配置文件监控"""
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            self.logger.info("配置文件监控已停止")
    
    def get_stats(self) -> ConfigStats:
        """获取配置管理统计信息"""
        return self._stats
    
    def clear_cache(self):
        """清理所有缓存"""
        self._cache.clear()
        self._validation_cache.clear()
        self.logger.info("配置缓存已清理")
    
    def create_from_template(self, template_type: str = 'development') -> Dict[str, Any]:
        """从模板创建配置"""
        if template_type in self._template_cache:
            return self._template_cache[template_type].copy()
        
        template_methods = {
            'development': ConfigTemplate.get_development_template,
            'production': ConfigTemplate.get_production_template,
            'testing': ConfigTemplate.get_testing_template
        }
        
        if template_type not in template_methods:
            raise ValueError(f"未知的模板类型: {template_type}")
        
        template = template_methods[template_type]()
        self._template_cache[template_type] = template
        return template.copy()
    
    def validate_config_file(self, config_path: Optional[Path] = None) -> bool:
        """验证配置文件"""
        path = config_path or self.config_path
        
        try:
            if not path.exists():
                self.logger.error(f"配置文件不存在: {path}")
                return False
            
            # 临时加载配置进行验证
            temp_manager = ConfigManager(path)
            config_data = temp_manager._load_config_file()
            config_data = temp_manager._apply_env_overrides(config_data)
            temp_manager._validate_config_data(config_data)
            
            # 尝试创建配置对象
            AppConfig(**config_data)
            
            self.logger.info(f"配置文件验证通过: {path}")
            return True
            
        except Exception as e:
            self.logger.error(f"配置文件验证失败: {path}, 错误: {str(e)}")
            return False
    
    def backup_config(self, backup_path: Optional[Path] = None) -> Path:
        """备份当前配置文件"""
        if backup_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = self.config_path.parent / f"{self.config_path.stem}_backup_{timestamp}{self.config_path.suffix}"
        
        try:
            import shutil
            shutil.copy2(self.config_path, backup_path)
            self.logger.info(f"配置文件已备份到: {backup_path}")
            return backup_path
        except Exception as e:
            self.logger.error(f"配置文件备份失败: {str(e)}")
            raise
    
    def cleanup(self):
        """清理资源"""
        self.stop_file_watcher()
        self.clear_cache()
        self._reload_callbacks.clear()
        self.logger.info("ConfigManager资源已清理")
    
    def _create_default_config(self):
        """创建默认配置文件"""
        default_config = {
            "qbittorrent": {
                "host": "localhost",
                "port": 8080,
                "username": "admin",
                "password": "password",
                "use_https": False,
                "verify_ssl": True,
                "use_nas_paths_directly": False,
                "path_mapping": [
                    {
                        "source_prefix": "/downloads",
                        "target_prefix": "/vol1/downloads",
                        "description": "本地到NAS的路径映射"
                    }
                ]
            },
            "deepseek": {
                "api_key": "",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
                "timeout": 30,
                "max_retries": 3,
                "retry_delay": 1.0,
                "few_shot_examples": [
                    {
                        "torrent_name": "Game.of.Thrones.S08E06.1080p.WEB.H264-MEMENTO",
                        "category": "tv"
                    },
                    {
                        "torrent_name": "Avengers.Endgame.2019.1080p.BluRay.x264-SPARKS",
                        "category": "movies"
                    }
                ]
            },
            "categories": {
                "tv": {
                    "savePath": "/downloads/tv/",
                    "keywords": ["S01", "S02", "剧集", "电视剧", "Series", "Episode"],
                    "description": "电视剧、连续剧、剧集等",
                    "priority": 10,
                    "rules": [
                        {
                            "type": "regex",
                            "pattern": r"S\d+E\d+",
                            "score": 5
                        },
                        {
                            "type": "keyword",
                            "keywords": ["Season", "Episode"],
                            "score": 3
                        }
                    ]
                },
                "movies": {
                    "savePath": "/downloads/movies/",
                    "keywords": ["电影", "Movie", "1080p", "4K", "BluRay", "Remux", "WEB-DL"],
                    "description": "电影作品",
                    "priority": 8,
                    "rules": [
                        {
                            "type": "regex",
                            "pattern": r"\.(19|20)\d{2}\.",
                            "score": 4
                        },
                        {
                            "type": "keyword", 
                            "keywords": ["1080p", "4K", "BluRay"],
                            "score": 3
                        }
                    ]
                },
                "adult": {
                    "savePath": "/downloads/adult/",
                    "keywords": ["成人", "18+", "xxx", "Porn", "Sex", "Nude", "JAV"],
                    "description": "成人内容",
                    "priority": 15,
                    "foreign_keywords": ["Brazzers", "Naughty America", "Reality Kings"]
                },
                "anime": {
                    "savePath": "/downloads/anime/",
                    "keywords": ["动画", "动漫", "Anime", "Fansub"],
                    "description": "日本动画、动漫",
                    "priority": 12
                },
                "music": {
                    "savePath": "/downloads/music/",
                    "keywords": ["音乐", "专辑", "Music", "Album", "FLAC", "MP3"],
                    "description": "音乐专辑、单曲",
                    "priority": 6
                },
                "games": {
                    "savePath": "/downloads/games/",
                    "keywords": ["游戏", "Game", "ISO", "PC", "PS5", "Switch"],
                    "description": "电子游戏",
                    "priority": 7
                },
                "software": {
                    "savePath": "/downloads/software/",
                    "keywords": ["软件", "Software", "App", "Crack", "Keygen"],
                    "description": "应用程序、软件",
                    "priority": 5
                },
                "other": {
                    "savePath": "/downloads/other/",
                    "keywords": [],
                    "description": "其他内容",
                    "priority": 1
                }
            },
            "check_interval": 2,
            "max_retries": 3,
            "retry_delay": 5,
            "notifications": {
                "enabled": False,
                "console": {
                    "enabled": True,
                    "colored": True,
                    "show_details": True,
                    "show_statistics": True
                },
                "services": [],
                "webhook_url": None
            },
            "hot_reload": True,
            "log_level": "INFO",
            "log_file": "magnet_monitor.log"
        }
        
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            self.logger.info(f"已创建默认配置文件: {self.config_path}")
        except Exception as e:
            from .exceptions import ConfigError
            raise ConfigError(f"创建默认配置失败: {str(e)}") from e
