"""FastAPI 应用主文件"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware

from ..config import Config, load_config
from ..qb_client import QBClient
from ..monitor import ClipboardMonitor
from ..classifier import ContentClassifier
from ..utils import extract_magnet_hash, get_magnet_display_name
from ..security import validate_magnet, sanitize_magnet

logger = logging.getLogger(__name__)


@dataclass
class MagnetHistoryItem:
    """历史记录项"""
    magnet: str
    hash: str
    category: str
    display_name: str
    timestamp: datetime
    status: str  # "success", "failed", "pending"
    error_message: Optional[str] = None


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: str
    level: str
    message: str
    source: str = ""


class WebMonitor:
    """Web 监控器 - 管理状态和 WebSocket 连接"""
    
    def __init__(self, config: Config):
        self.config = config
        self.qb_client: Optional[QBClient] = None
        self.monitor: Optional[ClipboardMonitor] = None
        self.classifier: Optional[ContentClassifier] = None
        
        # 历史记录
        self.history: List[MagnetHistoryItem] = []
        self.max_history = 1000
        
        # 日志队列
        self.logs: asyncio.Queue = asyncio.Queue(maxsize=500)
        self.recent_logs: List[LogEntry] = []
        self.max_logs = 200
        
        # WebSocket 连接管理
        self.active_connections: Set[WebSocket] = set()
        
        # 运行状态
        self.is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # 日志处理器
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志捕获"""
        class WebLogHandler(logging.Handler):
            def __init__(self, web_monitor: 'WebMonitor'):
                super().__init__()
                self.web_monitor = web_monitor
            
            def emit(self, record):
                try:
                    entry = LogEntry(
                        timestamp=datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                        level=record.levelname,
                        message=self.format(record),
                        source=record.name
                    )
                    # 异步添加到队列
                    asyncio.create_task(self.web_monitor._add_log(entry))
                except Exception:
                    pass
        
        handler = WebLogHandler(self)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        
        # 添加到根日志记录器
        logging.getLogger().addHandler(handler)
    
    async def _add_log(self, entry: LogEntry):
        """添加日志条目"""
        try:
            self.logs.put_nowait(entry)
            self.recent_logs.append(entry)
            if len(self.recent_logs) > self.max_logs:
                self.recent_logs.pop(0)
            
            # 广播给所有 WebSocket 连接
            await self.broadcast_log(entry)
        except asyncio.QueueFull:
            pass
    
    async def connect(self, websocket: WebSocket):
        """WebSocket 连接处理"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket 客户端连接，当前连接数: {len(self.active_connections)}")
        
        # 发送当前状态
        await self.send_status(websocket)
    
    def disconnect(self, websocket: WebSocket):
        """WebSocket 断开处理"""
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket 客户端断开，当前连接数: {len(self.active_connections)}")
    
    async def broadcast_log(self, entry: LogEntry):
        """广播日志给所有连接"""
        if not self.active_connections:
            return
        
        message = {
            "type": "log",
            "data": {
                "timestamp": entry.timestamp,
                "level": entry.level,
                "message": entry.message,
                "source": entry.source
            }
        }
        
        disconnected = set()
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                disconnected.add(conn)
        
        # 清理断开的连接
        for conn in disconnected:
            self.active_connections.discard(conn)
    
    async def broadcast_stats(self):
        """广播统计信息"""
        if not self.active_connections:
            return
        
        stats = self.get_stats()
        message = {
            "type": "stats",
            "data": stats
        }
        
        disconnected = set()
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                disconnected.add(conn)
        
        for conn in disconnected:
            self.active_connections.discard(conn)
    
    async def send_status(self, websocket: WebSocket):
        """发送当前状态给指定客户端"""
        try:
            await websocket.send_json({
                "type": "status",
                "data": {
                    "is_running": self.is_running,
                    "stats": self.get_stats(),
                    "config": self._get_safe_config()
                }
            })
        except Exception as e:
            logger.warning(f"发送状态失败: {e}")
    
    async def start_monitor(self):
        """启动剪贴板监控"""
        if self.is_running:
            return False, "监控已在运行"
        
        try:
            self.qb_client = QBClient(self.config)
            await self.qb_client.__aenter__()
            
            version = await self.qb_client.get_version()
            logger.info(f"qBittorrent 连接成功 (版本: {version})")
            
            # 确保分类存在
            await self.qb_client.ensure_categories()
            
            self.classifier = ContentClassifier(self.config)
            self.monitor = ClipboardMonitor(self.qb_client, self.config, self.classifier)
            
            # 注册回调
            self.monitor.add_handler(self._on_magnet_added)
            
            # 启动监控任务
            self._monitor_task = asyncio.create_task(self.monitor.start())
            self.is_running = True
            
            # 启动统计广播任务
            asyncio.create_task(self._broadcast_stats_loop())
            
            return True, f"监控已启动 (qBittorrent {version})"
        except Exception as e:
            logger.error(f"启动监控失败: {e}")
            return False, str(e)
    
    async def stop_monitor(self):
        """停止剪贴板监控"""
        if not self.is_running:
            return False, "监控未运行"
        
        try:
            self.is_running = False
            
            if self.monitor:
                self.monitor.stop()
            
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
                self._monitor_task = None
            
            if self.qb_client:
                await self.qb_client.__aexit__(None, None, None)
                self.qb_client = None
            
            return True, "监控已停止"
        except Exception as e:
            logger.error(f"停止监控失败: {e}")
            return False, str(e)
    
    async def add_magnet(self, magnet: str, category: Optional[str] = None) -> Dict[str, Any]:
        """手动添加磁力链接"""
        # 验证磁力链接
        is_valid, error = validate_magnet(magnet)
        if not is_valid:
            return {"success": False, "error": f"无效的磁力链接: {error}"}
        
        magnet = sanitize_magnet(magnet)
        magnet_hash = extract_magnet_hash(magnet) or magnet
        display_name = get_magnet_display_name(magnet)
        
        # 创建历史记录项
        history_item = MagnetHistoryItem(
            magnet=magnet,
            hash=magnet_hash,
            category=category or "unknown",
            display_name=display_name,
            timestamp=datetime.now(),
            status="pending"
        )
        self._add_history(history_item)
        
        if not self.qb_client:
            history_item.status = "failed"
            history_item.error_message = "未连接到 qBittorrent"
            return {"success": False, "error": "未连接到 qBittorrent"}
        
        try:
            # 如果没有指定分类，使用分类器
            if not category:
                from ..utils import parse_magnet
                name = parse_magnet(magnet) or display_name
                result = await self.classifier.classify(name)
                category = result.category
                history_item.category = category
            
            # 获取保存路径
            cat_config = self.config.categories.get(category)
            save_path = cat_config.save_path if cat_config else None
            
            # 添加到 qBittorrent
            success = await self.qb_client.add_torrent(magnet, category, save_path)
            
            if success:
                history_item.status = "success"
                return {
                    "success": True,
                    "category": category,
                    "hash": magnet_hash,
                    "display_name": display_name
                }
            else:
                history_item.status = "failed"
                history_item.error_message = "添加失败"
                return {"success": False, "error": "添加磁力链接失败"}
                
        except Exception as e:
            history_item.status = "failed"
            history_item.error_message = str(e)
            return {"success": False, "error": str(e)}
    
    def _on_magnet_added(self, magnet: str, category: str):
        """磁力链接添加回调"""
        magnet_hash = extract_magnet_hash(magnet) or magnet
        display_name = get_magnet_display_name(magnet)
        
        history_item = MagnetHistoryItem(
            magnet=magnet,
            hash=magnet_hash,
            category=category,
            display_name=display_name,
            timestamp=datetime.now(),
            status="success"
        )
        self._add_history(history_item)
    
    def _add_history(self, item: MagnetHistoryItem):
        """添加历史记录"""
        self.history.insert(0, item)
        if len(self.history) > self.max_history:
            self.history.pop()
        
        # 广播历史更新
        asyncio.create_task(self.broadcast_history_update(item))
    
    async def broadcast_history_update(self, item: MagnetHistoryItem):
        """广播历史记录更新"""
        if not self.active_connections:
            return
        
        message = {
            "type": "history_update",
            "data": self._history_item_to_dict(item)
        }
        
        disconnected = set()
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                disconnected.add(conn)
        
        for conn in disconnected:
            self.active_connections.discard(conn)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        monitor_stats = self.monitor.get_stats() if self.monitor else {}
        
        return {
            "is_running": self.is_running,
            "uptime_seconds": monitor_stats.get("uptime_seconds", 0),
            "total_processed": monitor_stats.get("total_processed", 0),
            "successful_adds": monitor_stats.get("successful_adds", 0),
            "failed_adds": monitor_stats.get("failed_adds", 0),
            "duplicates_skipped": monitor_stats.get("duplicates_skipped", 0),
            "invalid_magnets": monitor_stats.get("invalid_magnets", 0),
            "checks_performed": monitor_stats.get("checks_performed", 0),
            "clipboard_changes": monitor_stats.get("clipboard_changes", 0),
            "checks_per_minute": monitor_stats.get("checks_per_minute", 0),
            "avg_check_time_ms": monitor_stats.get("avg_check_time_ms", 0),
            "history_count": len(self.history),
        }
    
    def get_history(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """获取历史记录"""
        items = self.history[offset:offset + limit]
        return [self._history_item_to_dict(item) for item in items]
    
    def _history_item_to_dict(self, item: MagnetHistoryItem) -> Dict[str, Any]:
        """历史记录项转字典"""
        return {
            "hash": item.hash,
            "category": item.category,
            "display_name": item.display_name,
            "timestamp": item.timestamp.isoformat(),
            "status": item.status,
            "error_message": item.error_message
        }
    
    def get_categories(self) -> Dict[str, Any]:
        """获取分类配置"""
        return {
            name: {
                "save_path": cat.save_path,
                "keywords": cat.keywords
            }
            for name, cat in self.config.categories.items()
        }
    
    def update_category(self, name: str, save_path: str, keywords: List[str]) -> bool:
        """更新分类配置"""
        from ..config import CategoryConfig
        
        if name in self.config.categories:
            self.config.categories[name].save_path = save_path
            self.config.categories[name].keywords = keywords
        else:
            self.config.categories[name] = CategoryConfig(
                save_path=save_path,
                keywords=keywords
            )
        
        # 保存配置
        self.config.save()
        return True
    
    def delete_category(self, name: str) -> bool:
        """删除分类"""
        if name in self.config.categories:
            del self.config.categories[name]
            self.config.save()
            return True
        return False
    
    def _get_safe_config(self) -> Dict[str, Any]:
        """获取安全的配置（去除敏感信息）"""
        return {
            "qbittorrent": {
                "host": self.config.qbittorrent.host,
                "port": self.config.qbittorrent.port,
                "username": self.config.qbittorrent.username,
                "use_https": self.config.qbittorrent.use_https,
            },
            "ai": {
                "enabled": self.config.ai.enabled,
                "model": self.config.ai.model,
                "base_url": self.config.ai.base_url,
                "timeout": self.config.ai.timeout,
                "max_retries": self.config.ai.max_retries,
            },
            "categories": self.get_categories(),
            "check_interval": self.config.check_interval,
            "log_level": self.config.log_level,
        }
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """更新配置"""
        try:
            if "qbittorrent" in updates:
                qb = updates["qbittorrent"]
                self.config.qbittorrent.host = qb.get("host", self.config.qbittorrent.host)
                self.config.qbittorrent.port = qb.get("port", self.config.qbittorrent.port)
                self.config.qbittorrent.username = qb.get("username", self.config.qbittorrent.username)
                if "password" in qb and qb["password"]:
                    self.config.qbittorrent.password = qb["password"]
                self.config.qbittorrent.use_https = qb.get("use_https", self.config.qbittorrent.use_https)
            
            if "ai" in updates:
                ai = updates["ai"]
                self.config.ai.enabled = ai.get("enabled", self.config.ai.enabled)
                self.config.ai.model = ai.get("model", self.config.ai.model)
                self.config.ai.base_url = ai.get("base_url", self.config.ai.base_url)
                self.config.ai.timeout = ai.get("timeout", self.config.ai.timeout)
                self.config.ai.max_retries = ai.get("max_retries", self.config.ai.max_retries)
                if "api_key" in ai and ai["api_key"]:
                    self.config.ai.api_key = ai["api_key"]
            
            if "check_interval" in updates:
                self.config.check_interval = updates["check_interval"]
            
            if "log_level" in updates:
                self.config.log_level = updates["log_level"]
            
            self.config.save()
            return True
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            return False
    
    async def _broadcast_stats_loop(self):
        """定期广播统计信息"""
        while self.is_running:
            try:
                await self.broadcast_stats()
                await asyncio.sleep(5)  # 每 5 秒广播一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"广播统计信息失败: {e}")
                await asyncio.sleep(5)


# 全局 WebMonitor 实例
_web_monitor: Optional[WebMonitor] = None


def get_web_monitor() -> Optional[WebMonitor]:
    """获取 WebMonitor 实例"""
    return _web_monitor


def set_web_monitor(monitor: WebMonitor):
    """设置 WebMonitor 实例"""
    global _web_monitor
    _web_monitor = monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    monitor = get_web_monitor()
    if monitor and not monitor.is_running:
        await monitor.start_monitor()
    
    yield
    
    # 关闭时
    if monitor and monitor.is_running:
        await monitor.stop_monitor()


def create_app(config: Config) -> FastAPI:
    """创建 FastAPI 应用"""
    # 初始化 WebMonitor
    monitor = WebMonitor(config)
    set_web_monitor(monitor)
    
    app = FastAPI(
        title="qBittorrent Clipboard Monitor",
        description="qBittorrent 剪贴板监控 Web 管理界面",
        version="3.0.0",
        lifespan=lifespan
    )
    
    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 静态文件
    static_path = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    
    # 模板
    templates_path = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(templates_path))
    
    # 注册路由
    from . import routes
    routes.register_routes(app, templates)
    
    return app


async def run_web_server(config: Config, host: str = "0.0.0.0", port: int = 8080):
    """运行 Web 服务器"""
    import uvicorn
    
    app = create_app(config)
    
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )
    server = uvicorn.Server(config)
    
    logger.info(f"Web 服务器启动: http://{host}:{port}")
    await server.serve()
