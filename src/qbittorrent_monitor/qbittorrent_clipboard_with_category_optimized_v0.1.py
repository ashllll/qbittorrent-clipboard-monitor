"""
优化后的磁力链接监控与自动分类下载工具
版本: 2.0
优化内容：
1. 模块化代码结构
2. 增强错误处理
3. 支持异步操作
4. 改进配置管理
5. 增强安全性
"""

import asyncio
import json
import logging
import os
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Dict, Optional, Tuple
import aiohttp
import pyperclip
from pydantic import BaseModel, ValidationError
from openai import OpenAI

# ---------------------- 自定义异常 ----------------------
class ConfigError(Exception):
    """配置相关异常"""

class QBittorrentError(Exception):
    """qBittorrent操作异常"""

class NetworkError(QBittorrentError):
    """网络通信异常"""

# ---------------------- 数据模型 ----------------------
class CategoryConfig(BaseModel):
    """分类配置数据模型"""
    savePath: str
    keywords: list[str]
    description: str  # 添加分类描述字段
    foreign_keywords: Optional[list[str]] = None

class QBittorrentConfig(BaseModel):
    """qBittorrent配置数据模型"""
    host: str = "192.168.1.40"   
    port: int = 8989
    username: str = "llll"
    password: str = "128012"
    use_https: bool = False
    verify_ssl: bool = True

class DeepSeekConfig(BaseModel):
    """DeepSeek API配置数据模型"""
    api_key: str = "" # 默认为空，优先从环境变量读取
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    # 添加 Prompt 模板字段
    prompt_template: str = """你是一个专业的种子分类助手。请根据以下规则，将种子名称分类到最合适的类别中。

种子名称: {torrent_name}

可用分类及其描述:
{category_descriptions}

关键词提示:
{category_keywords}

分类要求：
1. 仔细分析种子名称中的关键词和特征，特别注意文件扩展名和分辨率信息。
2. 电视剧通常包含S01E01这样的季和集信息，或者包含"剧集"、"Season"、"Episode"等词。
3. 电影通常包含年份(如2020)、分辨率(1080p、4K)或"BluRay"、"WEB-DL"等标签。
4. 成人内容通常包含明显的成人关键词，或成人内容制作商名称。
5. 日本动画通常包含"动画"、"Anime"或"Fansub"等术语。
6. 如果同时符合多个分类，选择最合适的那个。
7. 如果无法确定分类或不属于任何明确分类，返回'other'。

请只返回最合适的分类名称（例如：tv, movies, adult, anime, music, games, software, other），不要包含任何其他解释或文字。"""

class AppConfig(BaseModel):
    """应用配置数据模型"""
    qbittorrent: QBittorrentConfig
    deepseek: DeepSeekConfig
    categories: Dict[str, CategoryConfig]
    path_mapping: Dict[str, str] = {}
    use_nas_paths_directly: bool = False
    check_interval: int = 2
    max_retries: int = 3
    retry_delay: int = 5

# ---------------------- 工具函数 ----------------------
def setup_logging() -> logging.Logger:
    """配置日志系统"""
    logger = logging.getLogger('MagnetMonitor')
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 文件处理器
    file_handler = logging.FileHandler('magnet_monitor.log')
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger

def parse_magnet(magnet_link: str) -> Tuple[Optional[str], Optional[str]]:
    """
    解析磁力链接，返回哈希值和名称
    :param magnet_link: 磁力链接字符串
    :return: (哈希值, 名称) 元组
    """
    hash_match = re.search(r"xt=urn:btih:([0-9a-fA-F]{40}|[0-9a-zA-Z]{32})", magnet_link)
    name_match = re.search(r"dn=([^&]+)", magnet_link)
    
    torrent_hash = hash_match.group(1).lower() if hash_match else None
    torrent_name = urllib.parse.unquote_plus(name_match.group(1)) if name_match else None
    
    return torrent_hash, torrent_name

# ---------------------- qBittorrent API客户端 ----------------------
class QBittorrentClient:
    """异步qBittorrent API客户端"""
    
    def __init__(self, config: QBittorrentConfig, app_config: Optional[AppConfig] = None, max_retries: int = 3, retry_delay: int = 5):
        self.config = config
        self.app_config = app_config
        self.session = aiohttp.ClientSession()
        self.logger = logging.getLogger('MagnetMonitor.QBittorrent')
        self._base_url = f"{'https' if config.use_https else 'http'}://{config.host}:{config.port}"
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    async def __aenter__(self):
        await self.login()
        return self
        
    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()
        
    async def login(self):
        """登录qBittorrent"""
        url = f"{self._base_url}/api/v2/auth/login"
        data = {
            'username': self.config.username,
            'password': self.config.password
        }
        
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"尝试登录 qBittorrent (尝试 {attempt + 1}/{self.max_retries})")
                async with self.session.post(url, data=data) as resp:
                    if resp.status == 200:
                        self.logger.info("成功登录qBittorrent")
                        return
                    elif resp.status == 403:
                        error_text = await resp.text()
                        self.logger.error(f"登录失败 - 权限不足: {error_text}")
                        if attempt < self.max_retries - 1:
                            self.logger.info(f"等待 {self.retry_delay} 秒后重试...")
                            await asyncio.sleep(self.retry_delay)
                            continue
                        raise NetworkError("登录失败 - 权限不足，请检查用户名和密码")
                    else:
                        error_text = await resp.text()
                        self.logger.error(f"登录失败 - 状态码: {resp.status}, 响应: {error_text}")
                        if attempt < self.max_retries - 1:
                            self.logger.info(f"等待 {self.retry_delay} 秒后重试...")
                            await asyncio.sleep(self.retry_delay)
                            continue
                        raise NetworkError(f"登录失败: {error_text}")
            except aiohttp.ClientError as e:
                self.logger.error(f"连接错误: {str(e)}")
                if attempt < self.max_retries - 1:
                    self.logger.info(f"等待 {self.retry_delay} 秒后重试...")
                    await asyncio.sleep(self.retry_delay)
                    continue
                raise NetworkError(f"连接失败: {str(e)}") from e
        
        raise NetworkError("登录失败，超过最大重试次数")

    async def ensure_categories(self, categories: Dict[str, CategoryConfig]):
        """确保所有分类存在，自动创建或更新"""
        try:
            # 获取现有分类
            url = f"{self._base_url}/api/v2/torrents/categories"
            self.logger.info(f"正在获取分类列表: {url}")
            
            async with self.session.get(url) as resp:
                # 检查状态码
                if resp.status != 200:
                    error_text = await resp.text()
                    self.logger.error(f"获取分类失败 - 状态码: {resp.status}, 响应: {error_text[:500]}...") # 限制日志输出长度
                    if resp.status == 403:
                        self.logger.error("权限不足，请检查用户权限设置")
                    raise QBittorrentError(f"获取分类失败: 状态码 {resp.status}")

                # 检查 Content-Type
                content_type = resp.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    error_text = await resp.text()
                    self.logger.error(f"获取分类失败 - 响应类型错误: {content_type}, 响应体: {error_text[:500]}...")
                    raise QBittorrentError(f"获取分类失败: 响应不是有效的 JSON (Content-Type: {content_type})")

                # 只有在检查通过后才解析 JSON
                try:
                    # 先读取文本，检查是否为空
                    response_text = await resp.text()
                    if not response_text:
                        self.logger.warning("获取分类失败 - qBittorrent API 返回了空响应体")
                        # 根据 ensure_categories 的逻辑，这里应该抛出异常，因为后续需要分类信息
                        raise QBittorrentError("获取分类失败: qBittorrent API 返回了空响应体")

                    # 尝试解析 JSON
                    existing_categories = json.loads(response_text) # 使用 json.loads 解析文本
                    self.logger.info(f"现有分类: {existing_categories}")

                except json.JSONDecodeError as json_error: # 捕获 json.loads 的解析错误
                    # response_text 变量已在上面获取
                    self.logger.error(f"获取分类失败 - JSON 解析错误: {json_error}, 响应体: {response_text[:500]}...")
                    raise QBittorrentError(f"获取分类失败: JSON 解析错误 - {json_error}") from json_error
                except aiohttp.ClientError as client_err: # 捕获可能的 aiohttp 错误
                    self.logger.error(f"读取分类响应体时发生网络错误: {client_err}")
                    raise QBittorrentError(f"获取分类失败: 读取响应体时出错 - {client_err}") from client_err

            # 创建或更新分类
            for name, config in categories.items():
                save_path = self._map_save_path(config.savePath)
                self.logger.info(f"处理分类: {name}, 保存路径: {save_path}")
                
                if name not in existing_categories:
                    self.logger.info(f"创建新分类: {name}")
                    await self._create_category(name, save_path)
                else:
                    # 如果分类已存在，跳过更新
                    self.logger.info(f"分类已存在: {name} (保存路径: {existing_categories[name]['savePath']})")
                    # 注释掉更新步骤
                    # self.logger.info(f"更新现有分类: {name}")
                    # await self._update_category(name, save_path)

        except aiohttp.ClientError as e:
            self.logger.error(f"网络错误: {str(e)}")
            raise NetworkError(f"分类操作失败: {str(e)}") from e
        except Exception as e:
            self.logger.error(f"未预期的错误: {str(e)}")
            raise QBittorrentError(f"分类操作失败: {str(e)}") from e

    async def _create_category(self, name: str, save_path: str):
        """创建新分类"""
        url = f"{self._base_url}/api/v2/torrents/createCategory"
        data = {'category': name, 'savePath': save_path}
        self.logger.info(f"创建分类请求: {url}, 数据: {data}")
        
        async with self.session.post(url, data=data) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                self.logger.error(f"创建分类失败 - 状态码: {resp.status}, 响应: {error_text}")
                raise QBittorrentError(f"创建分类失败: {error_text}")
            self.logger.info(f"创建分类成功: {name} -> {save_path}")

    async def _update_category(self, name: str, save_path: str):
        """更新现有分类"""
        url = f"{self._base_url}/api/v2/torrents/editCategory"
        data = {'category': name, 'savePath': save_path}
        self.logger.info(f"更新分类请求: {url}, 数据: {data}")
        
        async with self.session.post(url, data=data) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                self.logger.error(f"更新分类失败 - 状态码: {resp.status}, 响应: {error_text}")
                raise QBittorrentError(f"更新分类失败: {error_text}")
            self.logger.info(f"更新分类成功: {name} -> {save_path}")

    def _map_save_path(self, container_path: str) -> str:
        """映射容器路径到实际存储路径"""
        app_config = getattr(self, 'app_config', None)
        if not app_config:
            # 如果没有app_config，直接返回原路径
            return container_path
            
        if app_config.use_nas_paths_directly:
            # 直接使用NAS路径模式
            return container_path
            
        # 应用路径映射规则
        for container_prefix, nas_prefix in app_config.path_mapping.items():
            if container_path.startswith(container_prefix):
                mapped_path = container_path.replace(container_prefix, nas_prefix, 1)
                self.logger.debug(f"路径映射: {container_path} -> {mapped_path}")
                return mapped_path
                
        # 没有匹配的映射规则，返回原始路径
        return container_path

    async def get_existing_categories(self) -> Dict[str, str]:
        """获取现有的分类及其保存路径"""
        try:
            url = f"{self._base_url}/api/v2/torrents/categories"
            self.logger.info(f"正在获取分类列表: {url}")
            
            async with self.session.get(url) as resp:
                 # 检查状态码
                if resp.status != 200:
                    error_text = await resp.text()
                    self.logger.error(f"获取分类失败 - 状态码: {resp.status}, 响应: {error_text[:500]}...")
                    if resp.status == 403:
                        self.logger.error("权限不足，请检查用户权限设置")
                    # 在 get_existing_categories 中，我们可能不希望直接抛出异常中断流程，而是返回空字典
                    return {}

                # 检查 Content-Type
                content_type = resp.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    error_text = await resp.text()
                    self.logger.error(f"获取分类失败 - 响应类型错误: {content_type}, 响应体: {error_text[:500]}...")
                    return {}

                # 解析 JSON
                try:
                    categories = await resp.json()
                    self.logger.info(f"获取到现有分类: {categories}")
                    return categories
                except aiohttp.ContentTypeError as json_error:
                    error_text = await resp.text()
                    self.logger.error(f"获取分类失败 - JSON 解析错误: {json_error}, 响应体: {error_text[:500]}...")
                    return {}
                # 保留对其他可能的网络或意外错误的捕获
                except aiohttp.ClientError as client_err:
                    self.logger.error(f"获取分类时发生网络错误: {client_err}")
                    return {}
                except Exception as e:
                    import traceback
                    self.logger.error(f"获取分类时发生未预期错误: {str(e)}")
                    self.logger.debug(traceback.format_exc())
                    return {}
        # 添加外层 try 对应的 except 块以修复 Pylance 错误
        except aiohttp.ClientError as client_err:
             self.logger.error(f"获取分类时发生网络连接错误: {client_err}")
             return {}
        except Exception as e:
             import traceback
             self.logger.error(f"获取分类时发生未预期错误 (外层): {str(e)}")
             self.logger.debug(traceback.format_exc())
             return {}

    async def add_torrent(self, magnet_link: str, category: str) -> bool:
        """添加磁力链接，带重试机制"""
        for attempt in range(self.max_retries):
            try:
                torrent_hash, torrent_name = parse_magnet(magnet_link)
                if not torrent_hash:
                    self.logger.error("无效的磁力链接格式")
                    return False

                if await self._is_duplicate(torrent_hash):
                    self.logger.info(f"跳过重复种子: {torrent_hash[:8]}")
                    return False

                # 获取现有分类
                existing_categories = await self.get_existing_categories()
                
                url = f"{self._base_url}/api/v2/torrents/add"
                data = {
                    'urls': magnet_link,
                    'autoTMM': 'false'
                }

                # 如果分类存在，则使用该分类
                if category in existing_categories:
                    data['category'] = category
                    save_path = existing_categories[category]['savePath']
                    self.logger.info(f"种子将被添加到分类: {category} (保存路径: {save_path})")
                else:
                    self.logger.info("未找到匹配的分类，将使用默认下载路径")

                self.logger.info(f"添加种子请求: {url}")
                
                async with self.session.post(url, data=data) as resp:
                    if resp.status == 200 and await resp.text() != "Fails.":
                        self.logger.info(f"成功添加种子到分类: {category if category in existing_categories else '默认路径'}")
                        return True
                    elif resp.status == 403:
                        error_text = await resp.text()
                        self.logger.error(f"添加失败 - 权限不足: {error_text}")
                        if attempt < self.max_retries - 1:
                            self.logger.info(f"等待 {self.retry_delay} 秒后重试...")
                            await asyncio.sleep(self.retry_delay)
                            continue
                        return False
                    else:
                        error_text = await resp.text()
                        self.logger.error(f"添加失败 - 状态码: {resp.status}, 响应: {error_text}")
                        if attempt < self.max_retries - 1:
                            self.logger.info(f"等待 {self.retry_delay} 秒后重试...")
                            await asyncio.sleep(self.retry_delay)
                            continue
                        return False

            except aiohttp.ClientError as e:
                self.logger.warning(f"网络错误({attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    self.logger.info(f"等待 {self.retry_delay} 秒后重试...")
                    await asyncio.sleep(self.retry_delay)
                    continue
                return False

        self.logger.error("添加种子失败，超过最大重试次数")
        return False

    async def _is_duplicate(self, torrent_hash: str) -> bool:
        """检查种子是否已存在"""
        url = f"{self._base_url}/api/v2/torrents/info"
        params = {'hashes': torrent_hash}
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    return False
                torrents = await resp.json()
                return len(torrents) > 0
        except aiohttp.ClientError:
            return False

# ---------------------- qBittorrent 服务器发现 ----------------------
class QBittorrentDiscovery:
    """自动发现本地 qBittorrent 服务器"""
    
    def __init__(self):
        self.logger = logging.getLogger('MagnetMonitor.Discovery')
        self.common_ports = [8080, 8081, 8082, 8083, 8084, 8085, 8989, 9090]
        self.common_hosts = [
            "localhost",
            "127.0.0.1",
            "192.168.1.1",
            "192.168.1.100",
            "192.168.1.200",
            "192.168.1.254",
            "192.168.0.1",
            "192.168.0.100",
            "192.168.0.200",
            "192.168.0.254"
        ]
        
    async def discover(self) -> Optional[Tuple[str, int]]:
        """发现本地运行的 qBittorrent 服务器"""
        self.logger.info("开始搜索本地 qBittorrent 服务器...")
        
        for host in self.common_hosts:
            for port in self.common_ports:
                try:
                    url = f"http://{host}:{port}/api/v2/app/version"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=2) as response:
                            if response.status == 200:
                                self.logger.info(f"发现 qBittorrent 服务器: {host}:{port}")
                                return host, port
                except Exception as e:
                    continue
                    
        self.logger.warning("未找到本地 qBittorrent 服务器")
        return None

# ---------------------- 配置管理器 ----------------------
class ConfigManager:
    """配置管理器，支持环境变量覆盖和自动发现"""
    
    def __init__(self):
        self.logger = logging.getLogger('MagnetMonitor.Config')
        # 使用脚本同目录下的配置文件
        self.config_path = Path(__file__).parent / 'config.json'
        self.discovery = QBittorrentDiscovery()
        
    async def load_config(self) -> AppConfig:
        """加载并验证配置文件，支持环境变量覆盖和自动发现"""
        # 加载配置文件
        if not self.config_path.exists():
            self._create_default_config()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except Exception as e:
            raise ConfigError(f"配置文件读取失败: {str(e)}") from e

        # 环境变量覆盖
        config_data['qbittorrent'].update({
            'host': os.getenv('QBIT_HOST', config_data['qbittorrent']['host']),
            'port': int(os.getenv('QBIT_PORT', config_data['qbittorrent']['port'])),
            'username': os.getenv('QBIT_USER', config_data['qbittorrent']['username']),
            'password': os.getenv('QBIT_PASS', config_data['qbittorrent']['password'])
        })
        
        # 更新为DeepSeek配置名称
        if 'deepseek' in config_data:
            config_data['deepseek'].update({
                'api_key': os.getenv('DEEPSEEK_API_KEY', config_data['deepseek'].get('api_key', '')),
                'base_url': os.getenv('DEEPSEEK_BASE_URL', config_data['deepseek'].get('base_url', 'https://api.deepseek.com'))
            })

        # 确保 deepseek 配置存在
        if 'deepseek' not in config_data:
            raise ConfigError("配置文件中缺少 'deepseek' 部分")
        if not config_data['deepseek'].get('api_key'):
             self.logger.warning("DeepSeek API Key 未在配置或环境变量中设置，AI 分类功能可能无法使用。将使用规则引擎进行分类。")

        # 尝试自动发现服务器
        if config_data['qbittorrent']['host'] == "192.168.1.40":  # 如果是默认配置
            discovered = await self.discovery.discover()
            if discovered:
                host, port = discovered
                self.logger.info(f"使用自动发现的服务器配置: {host}:{port}")
                config_data['qbittorrent'].update({
                    'host': host,
                    'port': port
                })

        try:
            # 验证配置结构
            return AppConfig(**config_data)
        except ValidationError as e:
            raise ConfigError(f"配置验证错误: {str(e)}") from e

    def _create_default_config(self):
        """创建默认配置文件"""
        default_config = {
            "qbittorrent": {
                "host": "192.168.1.28", # 根据用户反馈更新默认主机地址
                "port": 8989,
                "username": "llll",
                "password": "128012",
                "use_https": False,
                "verify_ssl": True,
                "use_nas_paths_directly": False, # 移动到 qbittorrent 配置下
                "path_mapping": {             # 移动到 qbittorrent 配置下
                    "/downloads": "/vol1/downloads"
                }
            },
            "deepseek": {
                "api_key": "", # 请在此处或环境变量 DEEPSEEK_API_KEY 中填入您的 API Key
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com",
                "prompt_template": """你是一个专业的种子分类助手。请根据以下规则，将种子名称分类到最合适的类别中。

种子名称: {torrent_name}

可用分类及其描述:
{category_descriptions}

关键词提示:
{category_keywords}

分类要求：
1. 仔细分析种子名称中的关键词和特征，特别注意文件扩展名和分辨率信息。
2. 电视剧通常包含S01E01这样的季和集信息，或者包含"剧集"、"Season"、"Episode"等词。
3. 电影通常包含年份(如2020)、分辨率(1080p、4K)或"BluRay"、"WEB-DL"等标签。
4. 成人内容通常包含明显的成人关键词，或成人内容制作商名称。
5. 日本动画通常包含"动画"、"Anime"或"Fansub"等术语。
6. 如果同时符合多个分类，选择最合适的那个。
7. 如果无法确定分类或不属于任何明确分类，返回'other'。

请只返回最合适的分类名称（例如：tv, movies, adult, anime, music, games, software, other），不要包含任何其他解释或文字。"""
            },
            "categories": {
                "tv": {
                    "savePath": "/downloads/tv/",
                    "keywords": ["S01", "S02", "剧集", "电视剧", "Series", "Episode"],
                    "description": "电视剧、连续剧、剧集等。关键词如: S01, E01, Season, Episode, 剧集, 电视剧。",
                    "foreign_keywords": ["HBO", "Netflix", "Amazon Prime", "Hulu", "Apple TV+"]
                },
                "movies": {
                    "savePath": "/downloads/movies/",
                    "keywords": ["电影", "Movie", "1080p", "4K", "BluRay", "Remux", "WEB-DL"],
                    "description": "电影作品。关键词如: Movie, Film, 1080p, 4K, BluRay, Remux, WEB-DL, 电影。",
                    "foreign_keywords": []
                },
                "adult": {
                    "savePath": "/downloads/adult/",
                    "keywords": ["成人", "18+", "xxx", "Porn", "Sex", "Nude", "JAV"],
                    "description": "成人内容。关键词如: Adult, 18+, XXX, Porn, Sex, Nude, JAV, 以及常见成人内容制作商名称。",
                    "foreign_keywords": ["Brazzers", "Naughty America", "Reality Kings", "Blacked", "Vixen", "Tushy", "Deeper", "Evil Angel", "Wicked Pictures", "Digital Playground", "MetArt", "HegreArt"]
                },
                 "anime": {
                    "savePath": "/downloads/anime/",
                    "keywords": ["动画", "动漫", "Anime", "Fansub"],
                    "description": "日本动画、动漫剧集或电影。关键词如: Anime, Fansub, BDRip, 动画, 动漫。",
                    "foreign_keywords": []
                },
                "music": {
                    "savePath": "/downloads/music/",
                    "keywords": ["音乐", "专辑", "Music", "Album", "FLAC", "MP3"],
                    "description": "音乐专辑、单曲等。关键词如: Music, Album, FLAC, MP3, Lossless, 音乐, 专辑。",
                    "foreign_keywords": []
                },
                "games": {
                    "savePath": "/downloads/games/",
                    "keywords": ["游戏", "Game", "ISO", "PC", "PS5", "Switch"],
                    "description": "电子游戏。关键词如: Game, ISO, PC, PS4, PS5, Xbox, Switch, 游戏。",
                    "foreign_keywords": []
                },
                "software": {
                    "savePath": "/downloads/software/",
                    "keywords": ["软件", "Software", "App", "Crack", "Keygen"],
                    "description": "应用程序、软件。关键词如: Software, App, Crack, Keygen, 软件。",
                    "foreign_keywords": []
                },
                "other": {
                    "savePath": "/downloads/other/",
                    "keywords": [],
                    "description": "无法归入以上任何分类的其他内容。",
                    "foreign_keywords": []
                }
            },
            # 移除了顶层的 path_mapping 和 use_nas_paths_directly
            "check_interval": 2,
            "max_retries": 3,
            "retry_delay": 5
        }

        try:
            # 确保目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            self.logger.info(f"已创建默认配置文件: {self.config_path}")
        except Exception as e:
            raise ConfigError(f"创建默认配置失败: {str(e)}") from e

# ---------------------- 剪贴板监控器 ----------------------
class ClipboardMonitor:
    """异步剪贴板监控器"""
    
    def __init__(self, qbt: QBittorrentClient, config: AppConfig):
        self.qbt = qbt
        self.config = config
        self.logger = logging.getLogger('MagnetMonitor.Clipboard')
        self.last_clip = ""
        self.magnet_pattern = re.compile(
            r"^magnet:\?xt=urn:btih:[0-9a-fA-F]{40,}.*",
            re.IGNORECASE
        )
        self.ai_classifier = AIClassifier(config.deepseek)

    async def start(self):
        """启动剪贴板监控循环"""
        self.logger.info("开始监控剪贴板...")
        try:
            while True:
                await self._check_clipboard()
                await asyncio.sleep(self.config.check_interval)
        except asyncio.CancelledError:
            self.logger.info("监控已停止")
        except Exception as e:
            self.logger.error(f"监控异常: {str(e)}")
            raise

    async def _check_clipboard(self):
        """检查剪贴板内容"""
        try:
            current_clip = pyperclip.paste()
            if current_clip != self.last_clip and self.magnet_pattern.match(current_clip):
                self.last_clip = current_clip
                await self._process_magnet(current_clip)
        except pyperclip.PyperclipException as e:
            self.logger.error(f"剪贴板访问失败: {str(e)}")

    async def _process_magnet(self, magnet_link: str):
        """处理磁力链接"""
        self.logger.info(f"发现新磁力链接: {magnet_link[:60]}...")
        
        try:
            # 解析磁力链接
            torrent_hash, torrent_name = parse_magnet(magnet_link)
            if not torrent_hash:
                self.logger.error("无效的磁力链接格式")
                return

            # 使用 AI 进行分类
            category = await self.ai_classifier.classify(torrent_name, self.config.categories)
            self.logger.info(f"AI 分类结果: {category}")

            # 添加到qBittorrent
            if await self.qbt.add_torrent(magnet_link, category):
                self.logger.info(f"成功添加种子到分类: {category}")
            else:
                self.logger.warning("种子添加失败")

        except Exception as e:
            self.logger.error(f"处理磁力链接失败: {str(e)}")

# ---------------------- AI分类器 ----------------------
class AIClassifier:
    """使用 DeepSeek AI 进行种子分类"""
    
    def __init__(self, config: DeepSeekConfig):
        self.config = config
        self.logger = logging.getLogger('MagnetMonitor.AIClassifier')
        self.logger.info(f"初始化AI分类器: 模型={config.model}, API基础URL={config.base_url}")
        
        if not config.api_key:
            self.logger.warning("DeepSeek API Key 未配置，AI 分类器将不可用。")
            self.client = None # 或者引发配置错误
        else:
            self.logger.info(f"API Key配置成功: {config.api_key[:8]}...")
            # 修改为使用DeepSeek API
            try:
                self.client = OpenAI(
                    api_key=config.api_key,
                    base_url=config.base_url
                )
                self.logger.info("AI客户端初始化成功")
            except Exception as e:
                self.logger.error(f"AI客户端初始化失败: {str(e)}")
                self.client = None
        
    async def classify(self, torrent_name: Optional[str], categories: Dict[str, CategoryConfig]) -> str:
        """使用 AI 对种子进行分类"""
        if not self.client:
            self.logger.warning("AI 分类器未初始化 (缺少 API Key)，返回 'other'")
            return self._rule_based_classify(torrent_name, categories)
        if not torrent_name:
            self.logger.warning("种子名称为空，无法进行 AI 分类，返回 'other'")
            return "other"

        try:
            # 从配置构建分类描述字符串
            category_descriptions = "\n".join(
                [f"- {name}: {cfg.description}" for name, cfg in categories.items()]
            )
            
            # 构建分类关键词提示
            category_keywords = "\n".join(
                [f"- {name} 关键词: {', '.join(cfg.keywords + (cfg.foreign_keywords or []))}" 
                for name, cfg in categories.items() if cfg.keywords or cfg.foreign_keywords]
            )

            # 使用配置中的模板格式化 Prompt
            prompt = self.config.prompt_template.format(
                torrent_name=torrent_name,
                category_descriptions=category_descriptions,
                category_keywords=category_keywords
            )
            self.logger.debug(f"构建的 AI Prompt:\n{prompt}") # 记录完整的 Prompt 以便调试

            # 调用 AI API (修改为 DeepSeek 格式)
            completion = await asyncio.to_thread( # 在线程中运行同步的 OpenAI 调用
                self.client.chat.completions.create,
                model=self.config.model,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的种子分类助手，擅长根据文件名进行准确分类。请只返回最合适的分类名称，不要包含任何其他解释或文字。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # 获取并清理分类结果
            if completion.choices and completion.choices[0].message:
                 raw_category = completion.choices[0].message.content
                 if raw_category:
                    category = raw_category.strip().lower()
                    self.logger.info(f"AI 原始响应: '{raw_category}', 清理后分类: '{category}'")

                    # 验证分类结果是否在定义的分类中
                    if category in categories:
                        return category
                    else:
                        self.logger.warning(f"AI 返回的分类 '{category}' 不在预定义分类中，尝试使用规则引擎")
                        return self._rule_based_classify(torrent_name, categories)
                 else:
                    self.logger.warning("AI 返回了空消息内容，尝试使用规则引擎")
                    return self._rule_based_classify(torrent_name, categories)
            else:
                self.logger.warning("AI 响应结构不符合预期，尝试使用规则引擎")
                return self._rule_based_classify(torrent_name, categories)

        except ImportError: # 如果 openai 库未安装
             self.logger.error("OpenAI 库未安装，无法使用 AI 分类功能。请运行 'pip install openai'")
             self.client = None # 标记为不可用
             return self._rule_based_classify(torrent_name, categories)
        except Exception as e:
            # 更具体的错误记录
            import traceback
            self.logger.error(f"AI 分类失败: {type(e).__name__}: {str(e)}")
            self.logger.debug(traceback.format_exc()) # 记录详细堆栈信息到 debug 日志
            return self._rule_based_classify(torrent_name, categories)
            
    def _rule_based_classify(self, torrent_name: Optional[str], categories: Dict[str, CategoryConfig]) -> str:
        """基于规则的分类逻辑，当AI分类不可用或失败时使用"""
        if not torrent_name:
            return "other"
            
        self.logger.info(f"使用规则引擎分类: {torrent_name}")
            
        # 转换为小写以便不区分大小写匹配
        name_lower = torrent_name.lower()
        
        # 正则表达式模式
        tv_pattern = re.compile(r's\d+e\d+|season\s+\d+|episode\s+\d+|\d+x\d+', re.IGNORECASE)
        movie_year_pattern = re.compile(r'\.(19|20)\d{2}\.|\((19|20)\d{2}\)|\[(19|20)\d{2}\]')
        movie_quality_pattern = re.compile(r'1080p|720p|2160p|4k|uhd|bluray|web-?dl|hdtv', re.IGNORECASE)
        
        # 检查每个分类的关键词匹配
        matched_categories = {}
        
        # 检查是否匹配电视剧模式
        tv_match = tv_pattern.search(name_lower)
        if tv_match:
            matched_categories['tv'] = 5  # 高优先级
            self.logger.info(f"电视剧模式匹配: {tv_match.group(0)}")
            
        # 检查是否匹配电影年份/质量模式
        movie_year_match = movie_year_pattern.search(name_lower)
        movie_quality_match = movie_quality_pattern.search(name_lower)
        if movie_year_match or movie_quality_match:
            matched_categories['movies'] = 4
            matches = []
            if movie_year_match:
                matches.append(f"年份: {movie_year_match.group(0)}")
            if movie_quality_match:
                matches.append(f"质量: {movie_quality_match.group(0)}")
            self.logger.info(f"电影模式匹配: {', '.join(matches)}")
            
        # 遍历所有分类进行关键词匹配
        for cat_name, cat_config in categories.items():
            # 初始化匹配分数
            score = 0
            matched_keywords = []
            
            # 检查主要关键词
            for keyword in cat_config.keywords:
                if keyword.lower() in name_lower:
                    score += 2
                    matched_keywords.append(f"{keyword}(+2)")
                    
            # 检查外语关键词
            if cat_config.foreign_keywords:
                for keyword in cat_config.foreign_keywords:
                    if keyword.lower() in name_lower:
                        score += 3  # 外语关键词通常更具特异性
                        matched_keywords.append(f"{keyword}(+3)")
            
            if score > 0:
                # 如果已有匹配，则添加或更新分数
                if cat_name in matched_categories:
                    matched_categories[cat_name] += score
                else:
                    matched_categories[cat_name] = score
                self.logger.info(f"{cat_name} 分类匹配关键词: {', '.join(matched_keywords)}, 总分: {matched_categories[cat_name]}")
        
        # 找出得分最高的分类
        if matched_categories:
            best_category = max(matched_categories.items(), key=lambda x: x[1])[0]
            scores_display = ", ".join([f"{k}: {v}" for k, v in matched_categories.items()])
            self.logger.info(f"规则引擎分类结果: {best_category} (所有分数: {scores_display})")
            return best_category
            
        # 默认返回 other
        self.logger.info("规则引擎未找到匹配，返回 'other'")
        return "other"

# ---------------------- 主程序 ----------------------
async def main():
    """异步主函数"""
    logger = setup_logging()
    
    try:
        # 加载配置
        config_manager = ConfigManager()
        config = await config_manager.load_config()
        
        # 初始化qBittorrent客户端
        async with QBittorrentClient(
            config.qbittorrent,
            app_config=config,
            max_retries=config.max_retries,
            retry_delay=config.retry_delay
        ) as qbt:
            # 确保分类存在
            logger.info("正在检查并确保 qBittorrent 分类存在...")
            await qbt.ensure_categories(config.categories)
            logger.info("分类检查完成.")

            # 启动剪贴板监控
            logger.info("准备启动剪贴板监控...")
            await ClipboardMonitor(qbt, config).start()
            
    except ValidationError as e:
        logger.error(f"配置验证失败: {str(e)}")
        sys.exit(1)
    except QBittorrentError as e:
        logger.error(f"qBittorrent错误: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"未处理的异常: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
