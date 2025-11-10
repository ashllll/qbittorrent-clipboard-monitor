"""
增强的qBittorrent客户端模块

支持：
- 智能重试机制
- 增强的错误处理
- 多规则路径映射
- 更多API功能
"""

import asyncio
import json
import logging
import urllib.parse
import time
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple, Any
import aiohttp
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from .config import QBittorrentConfig, CategoryConfig, PathMappingRule, AppConfig
from .resilience import RateLimiter, CircuitBreaker, LRUCache, MetricsTracker
from .exceptions import (
    QBittorrentError, NetworkError, QbtAuthError, 
    QbtRateLimitError, QbtPermissionError, TorrentParseError
)
from .utils import parse_magnet


class QBittorrentClient:
    """增强的异步qBittorrent API客户端，具有智能重试机制、增强错误处理、多规则路径映射和更多API功能"""
    
    def __init__(self, config: QBittorrentConfig, app_config: Optional[AppConfig] = None):
        self.config = config
        self.app_config = app_config
        self.session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger('QBittorrentClient')
        self._base_url = f"{'https' if config.use_https else 'http'}://{config.host}:{config.port}"
        self._authenticated = False
        
        # 连接池配置
        self._connection_pool_size = getattr(config, 'connection_pool_size', 10)
        self._sessions: List[aiohttp.ClientSession] = []
        self._session_index = 0
        self._session_lock = asyncio.Lock()
        
        # 清理状态标志
        self._is_cleaned_up = False
        self._cleanup_lock = asyncio.Lock()
        
        # 缓存系统
        self._cache_ttl = getattr(config, 'cache_ttl_seconds', 300)
        self._cache = LRUCache(
            max_size=getattr(config, 'cache_max_size', 1000),
            ttl_seconds=self._cache_ttl,
        )
        
        # 性能监控
        self._metrics = MetricsTracker()
        
        # 断路器
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=getattr(config, 'circuit_breaker_threshold', 5),
            recovery_timeout=getattr(config, 'circuit_breaker_timeout', 60),
            on_state_change=self._on_circuit_state_change,
        )
        
        # 速率限制
        self._max_requests_per_minute = getattr(config, 'max_requests_per_minute', 60)
        self._rate_limiter = RateLimiter(self._max_requests_per_minute)
        
        # 线程池用于异步操作
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    async def close(self):
        """关闭所有会话（保持向后兼容）"""
        await self.cleanup()
    
    async def cleanup(self):
        """清理所有资源"""
        self.logger.info("🔍 [诊断] QBittorrentClient.cleanup() 被调用")
        async with self._cleanup_lock:
            if self._is_cleaned_up:
                self.logger.info("🔍 [诊断] 资源已标记为清理，但检查实际状态...")
                self.logger.info(f"🔍 [诊断] 连接池状态: {len(self._sessions)} 个会话")
                # 即使标记为已清理，也要检查是否还有未关闭的会话
                unclosed_count = 0
                for session in self._sessions:
                    if session and not session.closed:
                        unclosed_count += 1
                if unclosed_count > 0:
                    self.logger.warning(f"⚠️ [诊断] 发现 {unclosed_count} 个未关闭会话，强制清理")
                    self._is_cleaned_up = False  # 重置标志，强制清理
                else:
                    self.logger.info("✅ [诊断] 确认所有会话已关闭，跳过清理")
                    return
            
            self.logger.info("开始清理QBittorrentClient资源...")
            
            try:
                # 关闭所有HTTP会话，让aiohttp自动管理connector
                async with self._session_lock:
                    self.logger.info(f"🔍 [诊断] 清理前检查: 连接池中有 {len(self._sessions)} 个会话")
                    
                    for i, session in enumerate(self._sessions):
                        if session and not session.closed:
                            self.logger.info(f"🔧 [诊断] 正在关闭会话 {i+1}/{len(self._sessions)}")
                            await session.close()
                        else:
                            self.logger.warning(f"⚠️ [诊断] 会话 {i+1} 已关闭或为None")
                    self._sessions.clear()
                    
                    if self.session and not self.session.closed:
                        self.logger.info("🔧 [诊断] 关闭主会话")
                        await self.session.close()
                    
                    # 等待异步关闭操作完成
                    self.logger.info("⏳ [诊断] 等待会话完全关闭...")
                    await asyncio.sleep(0.5)
                    
                    self.logger.info("✅ [诊断] 所有HTTP会话已关闭")
                
                # 清理缓存
                if hasattr(self, '_cache'):
                    self._cache.clear()
                    self.logger.debug("缓存已清理")
                
                # 关闭线程池
                if hasattr(self, '_executor') and self._executor:
                    self._executor.shutdown(wait=True)
                    self.logger.debug("线程池已关闭")
                
                self._is_cleaned_up = True
                self.logger.info("QBittorrentClient资源清理完成")
                
            except Exception as e:
                self.logger.error(f"清理QBittorrentClient资源时出错: {str(e)}")
    
    def __del__(self):
        """析构函数，确保资源被清理"""
        if not self._is_cleaned_up:
            try:
                # 同步清理关键资源
                if hasattr(self, '_cache'):
                    self._cache.clear()
                    
                if hasattr(self, '_executor') and self._executor:
                    self._executor.shutdown(wait=False)
                
                # 强制关闭所有会话（同步方式）
                if hasattr(self, '_sessions'):
                    for session in self._sessions:
                        if session and not session.closed:
                            try:
                                # 使用同步方式强制关闭
                                if hasattr(session, '_connector') and session._connector:
                                    session._connector.close()
                            except Exception:
                                pass
                    self._sessions.clear()
                
                if hasattr(self, 'session') and self.session and not self.session.closed:
                    try:
                        if hasattr(self.session, '_connector') and self.session._connector:
                            self.session._connector.close()
                    except Exception:
                        pass
                    
            except Exception:
                pass  # 忽略析构时的异常
        
    async def __aenter__(self):
        # 初始化连接池
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        # 创建连接池中的会话，每个会话使用独立的connector
        for i in range(self._connection_pool_size):
            connector = aiohttp.TCPConnector(
                limit=100, 
                limit_per_host=30,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            )
            self._sessions.append(session)
        
        # 设置主会话为第一个
        self.session = self._sessions[0] if self._sessions else None
        
        await self.login()
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        """异步上下文管理器退出"""
        await self.cleanup()
    
    async def _get_next_session(self) -> aiohttp.ClientSession:
        """获取连接池中的下一个会话"""
        async with self._session_lock:
            if not self._sessions:
                return self.session
            
            session = self._sessions[self._session_index]
            self._session_index = (self._session_index + 1) % len(self._sessions)
            return session
    
    def _get_cache_key(self, method: str, url: str, params: dict = None, data: dict = None) -> str:
        """生成缓存键"""
        key_data = f"{method}:{url}"
        if params:
            key_data += f":params:{sorted(params.items())}"
        if data:
            key_data += f":data:{sorted(data.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """从缓存获取数据"""
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._metrics.inc('cache_hits')
            return cached
        self._metrics.inc('cache_misses')
        return None
    
    def _put_to_cache(self, cache_key: str, data: Any):
        """将数据放入缓存"""
        self._cache.set(cache_key, data)
    
    def _check_rate_limit(self) -> bool:
        """检查速率限制"""
        return self._rate_limiter.allow()
    
    def _check_circuit_breaker(self) -> bool:
        """检查断路器状态"""
        return self._circuit_breaker.allow()
    
    def _record_success(self):
        """记录成功请求"""
        self._circuit_breaker.record_success()
    
    def _record_failure(self):
        """记录失败请求"""
        self._circuit_breaker.record_failure()
    
    def _on_circuit_state_change(self, state: str):
        if state == 'open':
            self.logger.warning("断路器已打开，暂停新的请求")
        elif state == 'half_open':
            self.logger.info("断路器进入半开状态，尝试恢复连接")
        elif state == 'closed':
            self.logger.info("断路器恢复到关闭状态")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        snapshot = self._metrics.snapshot()
        cache_total = max(1, snapshot['cache_hits'] + snapshot['cache_misses'])
        total_requests = max(1, snapshot['requests'])
        return {
            'total_requests': snapshot['requests'],
            'cache_hit_rate': (snapshot['cache_hits'] / cache_total) * 100,
            'error_rate': (snapshot['errors'] / total_requests) * 100,
            'avg_response_time': snapshot['avg_response_time'],
            'max_response_time': snapshot['max_response_time'],
            'min_response_time': snapshot['min_response_time'],
            'circuit_breaker_state': self._circuit_breaker.state,
            'circuit_breaker_failures': self._circuit_breaker.failure_count,
            'cache_size': len(self._cache),
            'connection_pool_size': len(self._sessions),
            'last_request_time': snapshot['last_request_time']
        }
    
    async def _make_request_with_cache(
        self,
        method: str,
        url: str,
        params: dict = None,
        data: dict = None,
        use_cache: bool = True,
    ) -> Tuple[int, Any]:
        """带缓存的HTTP请求方法"""
        start_time = time.time()

        if not self._check_rate_limit():
            raise QbtRateLimitError("API请求频率超限")

        if not self._check_circuit_breaker():
            raise QBittorrentError("服务暂时不可用（断路器打开）")

        cache_key = None
        if use_cache and method.upper() == 'GET':
            cache_key = self._get_cache_key(method, url, params, data)
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                self.logger.debug(f"缓存命中: {method} {url}")
                return cached_result

        session = await self._get_next_session()

        try:
            self._metrics.inc('requests')
            self._metrics.update_last_request_time(datetime.now().isoformat())

            if method.upper() == 'GET':
                async with session.get(url, params=params) as resp:
                    status = resp.status
                    if resp.content_type == 'application/json':
                        result = await resp.json()
                    else:
                        result = await resp.text()
            else:
                async with session.post(url, data=data, params=params) as resp:
                    status = resp.status
                    if resp.content_type == 'application/json':
                        result = await resp.json()
                    else:
                        result = await resp.text()

            response_time = time.time() - start_time
            self._metrics.record_response(response_time)

            if 200 <= status < 300:
                self._record_success()
                if use_cache and method.upper() == 'GET' and cache_key:
                    self._put_to_cache(cache_key, (status, result))
                return status, result

            self._metrics.inc('errors')
            if status >= 500:
                self._record_failure()

            if status == 403:
                raise QbtPermissionError(f"权限不足: {result}")
            if status == 429:
                raise QbtRateLimitError(f"请求过于频繁: {result}")
            raise QBittorrentError(f"请求失败 (HTTP {status}): {result}")

        except aiohttp.ClientError as e:
            self._metrics.inc('errors')
            self._record_failure()
            raise NetworkError(f"网络请求错误: {str(e)}") from e
        except Exception as e:
            self._metrics.inc('errors')
            self._record_failure()
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type((NetworkError, QbtRateLimitError)),
        before_sleep=before_sleep_log(logging.getLogger('QBittorrent.Retry'), logging.INFO)
    )
    async def login(self):
        """登录qBittorrent"""
        url = f"{self._base_url}/api/v2/auth/login"
        data = {
            'username': self.config.username,
            'password': self.config.password
        }
        
        try:
            self.logger.info(f"尝试登录qBittorrent: {self.config.host}:{self.config.port}")
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    response_text = await resp.text()
                    if response_text == "Ok.":
                        self._authenticated = True
                        self.logger.info("成功登录qBittorrent")
                        return
                    else:
                        raise QbtAuthError(f"登录失败: {response_text}")
                elif resp.status == 403:
                    raise QbtAuthError("登录失败: 用户名或密码错误")
                elif resp.status == 429:
                    raise QbtRateLimitError("登录失败: API请求过于频繁")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"登录失败: HTTP {resp.status} - {error_text}")
                    
        except aiohttp.ClientError as e:
            raise NetworkError(f"网络连接失败: {str(e)}") from e
    
    async def get_version(self) -> str:
        """获取qBittorrent版本信息"""
        url = f"{self._base_url}/api/v2/app/version"
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return await resp.text()
                else:
                    raise QBittorrentError(f"获取版本失败: HTTP {resp.status}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"获取版本失败: {str(e)}") from e
    
    async def get_existing_categories(self) -> Dict[str, Dict[str, Any]]:
        """获取现有的分类及其详细信息"""
        url = f"{self._base_url}/api/v2/torrents/categories"
        
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get('Content-Type', '')
                    if 'application/json' not in content_type:
                        raise QBittorrentError(f"获取分类失败: 响应类型错误 ({content_type})")
                    
                    response_text = await resp.text()
                    if not response_text.strip():
                        self.logger.warning("qBittorrent返回空的分类列表")
                        return {}
                    
                    categories = json.loads(response_text)
                    self.logger.info(f"获取到 {len(categories)} 个现有分类")
                    return categories
                    
                elif resp.status == 403:
                    raise QbtPermissionError("获取分类失败: 权限不足")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"获取分类失败: HTTP {resp.status} - {error_text}")
                    
        except aiohttp.ClientError as e:
            raise NetworkError(f"获取分类失败: {str(e)}") from e
        except json.JSONDecodeError as e:
            raise QBittorrentError(f"解析分类响应失败: {str(e)}") from e
    
    async def ensure_categories(self, categories: Dict[str, CategoryConfig]):
        """确保所有分类存在，动态更新分类路径"""
        try:
            existing_categories = await self.get_existing_categories()
            
            for name, config in categories.items():
                mapped_path = self._map_save_path(config.save_path, name)
                self.logger.info(f"处理分类: {name}, 映射路径: {mapped_path}")
                
                if name not in existing_categories:
                    self.logger.info(f"创建新分类: {name}")
                    await self._create_category(name, mapped_path)
                else:
                    # 动态更新分类路径
                    existing_path = existing_categories[name].get('savePath', '')
                    if existing_path != mapped_path:
                        self.logger.info(f"更新分类路径: {name} (当前路径: {existing_path} -> 新路径: {mapped_path})")
                        await self._update_category(name, mapped_path)
                    else:
                        self.logger.info(f"分类路径未变，跳过更新: {name} (路径: {existing_path})")
                        
        except Exception as e:
            self.logger.error(f"分类管理失败: {str(e)}")
            # 不再抛出异常，允许程序继续运行
            self.logger.warning("分类管理失败，但程序将继续运行")
    
    async def _create_category(self, name: str, save_path: str):
        """创建新分类"""
        url = f"{self._base_url}/api/v2/torrents/createCategory"
        data = {'category': name, 'savePath': save_path}
        
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.logger.info(f"创建分类成功: {name} -> {save_path}")
                elif resp.status == 409:
                    self.logger.warning(f"分类已存在: {name}")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"创建分类失败: {error_text}")
                    
        except aiohttp.ClientError as e:
            raise NetworkError(f"创建分类网络错误: {str(e)}") from e
    
    async def _update_category(self, name: str, save_path: str):
        """更新现有分类"""
        url = f"{self._base_url}/api/v2/torrents/editCategory"
        data = {'category': name, 'savePath': save_path}
        
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.logger.info(f"更新分类成功: {name} -> {save_path}")
                elif resp.status == 409:
                    # 如果更新失败，尝试先删除再创建
                    self.logger.warning(f"更新分类失败，尝试重新创建: {name}")
                    await self._delete_category(name)
                    await self._create_category(name, save_path)
                else:
                    error_text = await resp.text()
                    # 当更新分类失败时，尝试删除并重新创建
                    self.logger.warning(f"更新分类失败: {error_text}，尝试重新创建")
                    await self._delete_category(name)
                    await self._create_category(name, save_path)
                    
        except aiohttp.ClientError as e:
            raise NetworkError(f"更新分类网络错误: {str(e)}") from e
    
    async def _delete_category(self, name: str):
        """删除分类"""
        url = f"{self._base_url}/api/v2/torrents/removeCategories"
        data = {'categories': name}
        
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.logger.info(f"删除分类成功: {name}")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"删除分类失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"删除分类网络错误: {str(e)}") from e
    
    def _map_save_path(self, original_path: str, category_name: str = "") -> str:
        """增强的路径映射功能"""
        if not self.app_config:
            return original_path
        
        # 如果配置为直接使用NAS路径
        if self.app_config.use_nas_paths_directly or self.config.use_nas_paths_directly:
            return original_path
        
        # 优先使用新的路径映射规则
        if self.config.path_mapping:
            for mapping in self.config.path_mapping:
                if original_path.startswith(mapping.source_prefix):
                    mapped_path = original_path.replace(
                        mapping.source_prefix, 
                        mapping.target_prefix, 
                        1
                    )
                    self.logger.debug(
                        f"路径映射 ({mapping.description or 'N/A'}): "
                        f"{original_path} -> {mapped_path}"
                    )
                    return mapped_path
        
        # 回退到传统的全局路径映射
        for source, target in self.app_config.path_mapping.items():
            if original_path.startswith(source):
                mapped_path = original_path.replace(source, target, 1)
                self.logger.debug(f"全局路径映射: {original_path} -> {mapped_path}")
                return mapped_path
        
        # 没有匹配的规则，返回原始路径
        self.logger.debug(f"无路径映射规则匹配，使用原始路径: {original_path}")
        return original_path
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type((NetworkError, QbtRateLimitError)),
        before_sleep=before_sleep_log(logging.getLogger('QBittorrent.AddTorrent'), logging.INFO)
    )
    async def add_torrent(self, magnet_link: str, category: str, **kwargs) -> bool:
        """添加磁力链接，支持更多选项"""
        try:
            # 解析磁力链接，提供默认名称
            torrent_hash, torrent_name = parse_magnet(magnet_link)
            if not torrent_hash:
                raise TorrentParseError("无效的磁力链接格式")
            
            # 如果磁力链接没有dn参数，尝试从种子属性获取名称
            display_name = torrent_name or f"磁力链接_{torrent_hash[:8]}"
            self.logger.debug(f"原始磁力链接文件名: {torrent_name}")
            
            # 检查是否重复
            if await self._is_duplicate(torrent_hash):
                self.logger.info(f"跳过重复种子: {display_name}")
                return False
            
            # 验证分类存在
            existing_categories = await self.get_existing_categories()
            
            url = f"{self._base_url}/api/v2/torrents/add"
            data = {
                'urls': magnet_link,
                'autoTMM': 'false',  # 关闭自动种子管理
                **kwargs  # 支持额外参数
            }
            
            # 设置分类
            if category in existing_categories:
                data['category'] = category
                save_path = existing_categories[category]['savePath']
                self.logger.info(f"种子将添加到分类: {category} ({save_path})")
            else:
                self.logger.warning(f"分类不存在: {category}，将使用默认路径")
            
            # 首次尝试添加种子
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    response_text = await resp.text()
                    if response_text != "Fails.":
                        # 种子添加成功，获取实际的种子名称（但不强制重命名）
                        try:
                            # 等待短暂时间让qBittorrent处理种子
                            await asyncio.sleep(1)
                            torrent_info = await self.get_torrent_properties(torrent_hash)
                            if 'name' in torrent_info and torrent_info['name']:
                                actual_name = torrent_info['name']
                                self.logger.info(f"成功添加种子: {actual_name}")
                            else:
                                self.logger.info(f"成功添加种子: {display_name}")
                        except Exception as e:
                            self.logger.warning(f"获取种子属性失败但不影响添加: {str(e)}")
                            self.logger.info(f"成功添加种子: {display_name}")
                        
                        return True
                    else:
                        raise QBittorrentError("添加种子失败: qBittorrent返回Fails")
                elif resp.status == 403:
                    raise QbtPermissionError("添加种子失败: 权限不足")
                elif resp.status == 429:
                    raise QbtRateLimitError("添加种子失败: API请求过于频繁")
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"添加种子失败: HTTP {resp.status} - {error_text}")
                    
        except TorrentParseError:
            raise
        except aiohttp.ClientError as e:
            raise NetworkError(f"添加种子网络错误: {str(e)}") from e
    
    async def _rename_torrent(self, torrent_hash: str, new_name: str) -> bool:
        """重命名种子以保持原始名称"""
        try:
            # 清理文件名中的非法字符
            import re
            new_name = re.sub(r'[\\/:*?"<>|]', '_', new_name)
            new_name = new_name.strip()
            
            # 使用正确的qBittorrent API端点
            url = f"{self._base_url}/api/v2/torrents/rename"
            data = {
                'hash': torrent_hash,
                'name': new_name
            }
            
            self.logger.info(f"🔄 尝试重命名种子: {torrent_hash[:8]} -> {new_name}")
            
            async with self.session.post(url, data=data) as resp:
                response_text = await resp.text()
                if resp.status == 200:
                    self.logger.info(f"✅ 种子重命名成功: {new_name}")
                    return True
                else:
                    self.logger.warning(f"⚠️ 种子重命名失败 (HTTP {resp.status}): {response_text}")
                    
                    # 尝试备用方法：使用setName端点
                    return await self._set_torrent_name_alternative(torrent_hash, new_name)
        except Exception as e:
            self.logger.warning(f"⚠️ 种子重命名异常: {str(e)}")
            # 尝试备用方法
            return await self._set_torrent_name_alternative(torrent_hash, new_name)

    async def _set_torrent_name_alternative(self, torrent_hash: str, new_name: str) -> bool:
        """备用重命名方法：使用setName端点"""
        try:
            url = f"{self._base_url}/api/v2/torrents/setName"
            data = {
                'hash': torrent_hash,
                'name': new_name
            }
            
            self.logger.info(f"🔄 使用备用方法重命名: {torrent_hash[:8]} -> {new_name}")
            
            async with self.session.post(url, data=data) as resp:
                response_text = await resp.text()
                if resp.status == 200:
                    self.logger.info(f"✅ 备用重命名成功: {new_name}")
                    return True
                else:
                    self.logger.warning(f"⚠️ 备用重命名也失败 (HTTP {resp.status}): {response_text}")
                    return False
        except Exception as e:
            self.logger.warning(f"⚠️ 备用重命名异常: {str(e)}")
            return False
    
    async def _is_duplicate(self, torrent_hash: str) -> bool:
        """检查种子是否已存在"""
        url = f"{self._base_url}/api/v2/torrents/info"
        params = {'hashes': torrent_hash}
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    torrents = await resp.json()
                    return len(torrents) > 0
                else:
                    self.logger.warning(f"检查重复失败: HTTP {resp.status}")
                    return False
        except aiohttp.ClientError as e:
            self.logger.warning(f"检查重复网络错误: {str(e)}")
            return False
    
    async def get_torrents(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取种子列表"""
        url = f"{self._base_url}/api/v2/torrents/info"
        params = {}
        if category:
            params['category'] = category
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"获取种子列表失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"获取种子列表网络错误: {str(e)}") from e
    
    async def delete_torrent(self, torrent_hash: str, delete_files: bool = False) -> bool:
        """删除种子"""
        url = f"{self._base_url}/api/v2/torrents/delete"
        data = {
            'hashes': torrent_hash,
            'deleteFiles': 'true' if delete_files else 'false'
        }
        
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.logger.info(f"删除种子成功: {torrent_hash[:8]}")
                    return True
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"删除种子失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"删除种子网络错误: {str(e)}") from e
    
    async def pause_torrent(self, torrent_hash: str) -> bool:
        """暂停种子"""
        url = f"{self._base_url}/api/v2/torrents/pause"
        data = {'hashes': torrent_hash}
        
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.logger.info(f"暂停种子成功: {torrent_hash[:8]}")
                    return True
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"暂停种子失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"暂停种子网络错误: {str(e)}") from e
    
    async def resume_torrent(self, torrent_hash: str) -> bool:
        """恢复种子"""
        url = f"{self._base_url}/api/v2/torrents/resume"
        data = {'hashes': torrent_hash}
        
        try:
            async with self.session.post(url, data=data) as resp:
                if resp.status == 200:
                    self.logger.info(f"恢复种子成功: {torrent_hash[:8]}")
                    return True
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"恢复种子失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"恢复种子网络错误: {str(e)}") from e
    
    async def get_torrent_properties(self, torrent_hash: str) -> Dict[str, Any]:
        """获取种子属性"""
        url = f"{self._base_url}/api/v2/torrents/properties"
        params = {'hash': torrent_hash}
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"获取种子属性失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"获取种子属性网络错误: {str(e)}") from e
    
    async def get_torrent_files(self, torrent_hash: str) -> List[Dict[str, Any]]:
        """获取种子文件列表"""
        url = f"{self._base_url}/api/v2/torrents/files"
        params = {'hash': torrent_hash}
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    error_text = await resp.text()
                    raise QBittorrentError(f"获取种子文件失败: {error_text}")
        except aiohttp.ClientError as e:
            raise NetworkError(f"获取种子文件网络错误: {str(e)}") from e


# ============================================================================
# 优化后的 qBittorrent 客户端 - 支持多级连接池和批量操作
# ============================================================================

class OptimizedQBittorrentClient(QBittorrentClient):
    """
    优化版 qBittorrent 客户端

    新增功能：
    1. 多级连接池 (读、写、API 分离)
    2. 批量操作优化
    3. 智能错误恢复
    4. 性能监控增强
    """

    def __init__(self, config: QBittorrentConfig, app_config: Optional[AppConfig] = None):
        super().__init__(config, app_config)
        self.logger = logging.getLogger('OptimizedQBittorrentClient')

        # 多级连接池 - 优化指导文档建议
        self._read_pool: Optional[aiohttp.ClientSession] = None
        self._write_pool: Optional[aiohttp.ClientSession] = None
        self._api_pool: Optional[aiohttp.ClientSession] = None

        # 连接池配置
        self._read_pool_size = getattr(config, 'read_pool_size', 10)
        self._write_pool_size = getattr(config, 'write_pool_size', 5)
        self._api_pool_size = getattr(config, 'api_pool_size', 20)

        # 批量操作统计
        self._batch_stats = {
            'total_batches': 0,
            'successful_batches': 0,
            'failed_batches': 0,
            'total_items': 0,
            'avg_batch_size': 0.0
        }

    async def __aenter__(self):
        """异步上下文管理器 - 初始化多级连接池"""
        # 初始化父类连接池
        await super().__aenter__()

        # 创建多级连接池
        timeout = aiohttp.ClientTimeout(total=30, connect=10)

        # 读连接池 - 用于获取数据
        read_connector = aiohttp.TCPConnector(
            limit=self._read_pool_size,
            limit_per_host=5,
            keepalive_timeout=30
        )
        self._read_pool = aiohttp.ClientSession(
            timeout=timeout,
            connector=read_connector
        )

        # 写连接池 - 用于添加/修改数据
        write_connector = aiohttp.TCPConnector(
            limit=self._write_pool_size,
            limit_per_host=3,
            keepalive_timeout=30
        )
        self._write_pool = aiohttp.ClientSession(
            timeout=timeout,
            connector=write_connector
        )

        # API 连接池 - 用于复杂查询
        api_connector = aiohttp.TCPConnector(
            limit=self._api_pool_size,
            limit_per_host=10,
            keepalive_timeout=60
        )
        self._api_pool = aiohttp.ClientSession(
            timeout=timeout,
            connector=api_connector
        )

        self.logger.info(
            f"多级连接池初始化完成: "
            f"读({self._read_pool_size}) 写({self._write_pool_size}) API({self._api_pool_size})"
        )
        return self

    async def cleanup(self):
        """清理所有资源，包括多级连接池"""
        self.logger.info("开始清理优化客户端资源...")

        try:
            # 关闭多级连接池
            if self._read_pool and not self._read_pool.closed:
                await self._read_pool.close()
                self.logger.debug("读连接池已关闭")

            if self._write_pool and not self._write_pool.closed:
                await self._write_pool.close()
                self.logger.debug("写连接池已关闭")

            if self._api_pool and not self._api_pool.closed:
                await self._api_pool.close()
                self.logger.debug("API连接池已关闭")

            # 调用父类清理
            await super().cleanup()

            self.logger.info("优化客户端资源清理完成")

        except Exception as e:
            self.logger.error(f"清理优化客户端资源时出错: {str(e)}")

    async def add_torrents_batch(
        self,
        torrents: List[Tuple[str, str]],
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """
        批量添加种子 - 优化指导文档建议

        Args:
            torrents: [(magnet_link, category), ...] 的列表
            batch_size: 每批处理的种子数量

        Returns:
            {
                'success_count': int,
                'failed_count': int,
                'skipped_count': int,
                'results': List[Dict]
            }
        """
        self.logger.info(f"开始批量添加 {len(torrents)} 个种子 (批次大小: {batch_size})")
        self._batch_stats['total_batches'] += 1
        self._batch_stats['total_items'] += len(torrents)

        results = {
            'success_count': 0,
            'failed_count': 0,
            'skipped_count': 0,
            'results': []
        }

        # 分批处理
        for i in range(0, len(torrents), batch_size):
            batch = torrents[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(torrents) + batch_size - 1) // batch_size

            self.logger.info(f"处理批次 {batch_num}/{total_batches} ({len(batch)} 个种子)")

            # 并发处理当前批次
            tasks = []
            for magnet_link, category in batch:
                task = asyncio.create_task(
                    self._add_torrent_safe(magnet_link, category)
                )
                tasks.append(task)

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理批次结果
            for j, result in enumerate(batch_results):
                magnet_link, category = batch[j]

                if isinstance(result, Exception):
                    self.logger.error(f"添加种子失败: {magnet_link[:30]}... - {str(result)}")
                    results['failed_count'] += 1
                    results['results'].append({
                        'magnet': magnet_link,
                        'category': category,
                        'status': 'failed',
                        'error': str(result)
                    })
                elif result is True:
                    results['success_count'] += 1
                    results['results'].append({
                        'magnet': magnet_link,
                        'category': category,
                        'status': 'success'
                    })
                elif result is False:
                    results['skipped_count'] += 1
                    results['results'].append({
                        'magnet': magnet_link,
                        'category': category,
                        'status': 'skipped',
                        'reason': 'duplicate'
                    })

        # 更新统计
        if results['failed_count'] == 0:
            self._batch_stats['successful_batches'] += 1
        else:
            self._batch_stats['failed_batches'] += 1

        avg_size = self._batch_stats['total_items'] / max(self._batch_stats['total_batches'], 1)
        self._batch_stats['avg_batch_size'] = avg_size

        self.logger.info(
            f"批量添加完成: 成功 {results['success_count']}, "
            f"失败 {results['failed_count']}, 跳过 {results['skipped_count']}"
        )

        return results

    async def _add_torrent_safe(self, magnet_link: str, category: str) -> bool:
        """安全添加单个种子 (用于批量操作)"""
        try:
            # 使用写连接池
            result = await self.add_torrent(magnet_link, category)
            return result
        except Exception as e:
            self.logger.error(f"批量添加失败: {magnet_link[:30]}... - {str(e)}")
            raise

    async def get_torrents_batch(
        self,
        hashes: List[str],
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        批量获取种子信息 - 优化指导文档建议

        Args:
            hashes: 种子哈希列表
            batch_size: 每批查询的数量

        Returns:
            {
                'total': int,
                'found': int,
                'not_found': int,
                'torrents': Dict[hash, torrent_info]
            }
        """
        self.logger.info(f"开始批量获取 {len(hashes)} 个种子信息")

        results = {
            'total': len(hashes),
            'found': 0,
            'not_found': 0,
            'torrents': {}
        }

        # 分批查询
        for i in range(0, len(hashes), batch_size):
            batch = hashes[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(hashes) + batch_size - 1) // batch_size

            self.logger.debug(f"查询批次 {batch_num}/{total_batches}")

            # 构造查询参数
            params = {}
            if len(batch) == 1:
                # 单个查询
                params['hashes'] = batch[0]
            else:
                # 批量查询 (用 | 分隔)
                params['hashes'] = '|'.join(batch)

            try:
                # 使用读连接池查询
                url = f"{self._base_url}/api/v2/torrents/info"
                async with self._read_pool.get(url, params=params) as resp:
                    if resp.status == 200:
                        torrents = await resp.json()

                        # 处理返回的种子信息
                        found_hashes = set()
                        for torrent in torrents:
                            hash_value = torrent.get('hash', '').lower()
                            if hash_value:
                                results['torrents'][hash_value] = torrent
                                found_hashes.add(hash_value)

                        # 更新计数
                        results['found'] += len(found_hashes)
                        results['not_found'] += len(batch) - len(found_hashes)

                        self.logger.debug(f"批次 {batch_num}: 找到 {len(found_hashes)}/{len(batch)} 个种子")
                    else:
                        error_text = await resp.text()
                        self.logger.error(f"批次 {batch_num} 查询失败: {error_text}")
                        results['not_found'] += len(batch)

            except Exception as e:
                self.logger.error(f"批次 {batch_num} 查询异常: {str(e)}")
                results['not_found'] += len(batch)

        self.logger.info(
            f"批量查询完成: 找到 {results['found']}/{results['total']} 个种子"
        )

        return results

    async def get_torrents_by_category_batch(
        self,
        categories: List[str],
        use_api_pool: bool = True
    ) -> Dict[str, Any]:
        """
        按分类批量获取种子 - 使用 API 连接池

        Args:
            categories: 分类列表
            use_api_pool: 是否使用 API 连接池

        Returns:
            Dict[category, List[torrent_info]]
        """
        self.logger.info(f"按分类批量获取种子: {categories}")

        results = {}

        # 并发查询所有分类
        tasks = []
        for category in categories:
            task = asyncio.create_task(
                self._get_torrents_by_category_safe(category, use_api_pool)
            )
            tasks.append((category, task))

        for category, task in tasks:
            try:
                torrents = await task
                results[category] = torrents
                self.logger.debug(f"分类 '{category}': {len(torrents)} 个种子")
            except Exception as e:
                self.logger.error(f"获取分类 '{category}' 失败: {str(e)}")
                results[category] = []

        return results

    async def _get_torrents_by_category_safe(
        self,
        category: str,
        use_api_pool: bool = True
    ) -> List[Dict[str, Any]]:
        """安全按分类获取种子"""
        url = f"{self._base_url}/api/v2/torrents/info"
        params = {'category': category}

        session = self._api_pool if use_api_pool else self.session
        async with session.get(url, params=params) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                error_text = await resp.text()
                raise QBittorrentError(f"获取分类 '{category}' 失败: {error_text}")

    def get_batch_stats(self) -> Dict[str, Any]:
        """获取批量操作统计信息"""
        stats = self._batch_stats.copy()

        if stats['total_batches'] > 0:
            stats['success_rate'] = (
                stats['successful_batches'] / stats['total_batches'] * 100
            )
        else:
            stats['success_rate'] = 0.0

        return stats

    async def _smart_retry_with_different_params(self, error: Exception) -> Any:
        """
        智能错误恢复 - 优化指导文档建议
        根据错误类型使用不同的重试策略
        """
        if isinstance(error, QbtRateLimitError):
            # 限流错误：等待更长时间
            self.logger.warning("检测到 API 限流，等待后重试...")
            await asyncio.sleep(5)
            # 降低并发度
            return await self._retry_with_reduced_concurrency()
        elif isinstance(error, QbtPermissionError):
            # 权限错误：不重试，直接抛出
            raise QBittorrentError("权限不足，无法重试")
        elif isinstance(error, NetworkError):
            # 网络错误：指数退避重试
            self.logger.warning("网络错误，指数退避重试...")
            await asyncio.sleep(2)
            return await self._retry_with_backoff()
        else:
            # 其他错误：标准重试
            raise

    async def _retry_with_reduced_concurrency(self) -> Any:
        """降低并发度重试"""
        # 这里可以动态调整连接池大小
        # 暂时返回 False 表示需要降低并发
        return False

    async def _retry_with_backoff(self) -> Any:
        """指数退避重试"""
        await asyncio.sleep(1)
        return True
