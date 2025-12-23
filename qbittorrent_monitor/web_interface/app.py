"""
Web管理界面主应用

提供Web UI管理qBittorrent剪贴板监控器
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional, Literal
from enum import Enum
import asyncio
import json
import logging
import os
from datetime import datetime
import uvicorn

from ..config import AppConfig
from ..qbittorrent_client_enhanced import EnhancedQBittorrentClient
from ..monitoring import get_metrics_collector, get_health_checker
from ..circuit_breaker import get_global_traffic_controller
from ..__version__ import __version__, PROJECT_DESCRIPTION

logger = logging.getLogger(__name__)


# ============================================================================
# 安全配置 - 使用环境变量控制
# ============================================================================

class SecurityConfig:
    """安全配置管理"""
    
    @staticmethod
    def get_allowed_origins() -> List[str]:
        """从环境变量获取允许的来源列表"""
        env_origins = os.getenv("ALLOWED_ORIGINS", "")
        if env_origins:
            return [origin.strip() for origin in env_origins.split(",")]
        # 默认只允许本地开发
        return ["http://localhost:8000", "http://127.0.0.1:8000"]
    
    @staticmethod
    def get_allowed_hosts() -> List[str]:
        """从环境变量获取允许的主机列表"""
        env_hosts = os.getenv("ALLOWED_HOSTS", "")
        if env_hosts:
            return [host.strip() for host in env_hosts.split(",")]
        return ["localhost", "127.0.0.1"]


# ============================================================================
# WebSocket 消息模型 - 输入验证
# ============================================================================

class WebSocketMessageType(str, Enum):
    """WebSocket 消息类型枚举"""
    PING = "ping"
    PONG = "pong"
    STATS_REQUEST = "stats_request"
    STATS_UPDATE = "stats_update"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    ERROR = "error"


class WebSocketMessage(BaseModel):
    """WebSocket 消息模型 - 带输入验证"""
    type: WebSocketMessageType
    data: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = Field(None, max_length=64)
    
    class Config:
        extra = "forbid"  # 禁止额外字段


class APIResponse(BaseModel):
    """统一 API 响应格式"""
    success: bool
    data: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @classmethod
    def success(cls, data: Any = None, meta: Dict = None) -> "APIResponse":
        return cls(success=True, data=data, error=None, meta=meta or {})
    
    @classmethod
    def error(cls, message: str, code: str = "UNKNOWN_ERROR", details: Dict = None) -> "APIResponse":
        return cls(
            success=False,
            data=None,
            error={
                "code": code,
                "message": message,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat()
            }
        )


class WebSocketManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"WebSocket客户端已连接，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket客户端已断开，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """广播消息到所有连接的客户端"""
        if not self.active_connections:
            return

        message_str = json.dumps(jsonable_encoder(message), default=str)

        async with self._lock:
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(message_str)
                except Exception as e:
                    logger.debug(f"WebSocket发送失败，连接已断开: {str(e)}")
                    disconnected.append(connection)

            # 清理断开的连接
            for ws in disconnected:
                if ws in self.active_connections:
                    self.active_connections.remove(ws)


class WebInterface:
    """Web界面管理器"""

    def __init__(self, config: AppConfig, qbt_client: EnhancedQBittorrentClient):
        self.config = config
        self.qbt_client = qbt_client
        self.app = FastAPI(
            title=PROJECT_DESCRIPTION,
            description="Web管理界面",
            version=__version__
        )

        # WebSocket管理器
        self.ws_manager = WebSocketManager()

        # 全局组件
        self.metrics_collector = get_metrics_collector()
        self.health_checker = get_health_checker()
        self.traffic_controller = get_global_traffic_controller()

        # 配置CORS - 使用安全配置
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=SecurityConfig.get_allowed_origins(),  # 从环境变量读取
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # 明确列出方法
            allow_headers=["Content-Type", "Authorization", "X-Request-ID"],  # 明确列出头
        )

        # 挂载静态文件和模板
        self._setup_routes()

        # 启动WebSocket广播任务
        self._broadcast_task: Optional[asyncio.Task] = None

    def _setup_routes(self):
        """设置路由"""

        # 主页
        @self.app.get("/", response_class=HTMLResponse)
        async def index(request: Request):
            return self.templates.TemplateResponse(
                "index.html",
                {"request": request, "title": "控制台"}
            )

        @self.app.get("/torrents", response_class=HTMLResponse)
        async def torrents_page(request: Request):
            return self.templates.TemplateResponse(
                "torrents.html",
                {"request": request, "title": "种子管理"}
            )

        @self.app.get("/stats", response_class=HTMLResponse)
        async def stats_page(request: Request):
            return self.templates.TemplateResponse(
                "stats.html",
                {"request": request, "title": "统计信息"}
            )

        @self.app.get("/settings", response_class=HTMLResponse)
        async def settings_page(request: Request):
            return self.templates.TemplateResponse(
                "settings.html",
                {"request": request, "title": "设置"}
            )

        @self.app.get("/workflow", response_class=HTMLResponse)
        async def workflow_page(request: Request):
            return self.templates.TemplateResponse(
                "workflow.html",
                {"request": request, "title": "工作流管理"}
            )

        @self.app.get("/rss", response_class=HTMLResponse)
        async def rss_page(request: Request):
            return self.templates.TemplateResponse(
                "rss.html",
                {"request": request, "title": "RSS订阅管理"}
            )

        # API接口

        # 获取种子列表
        @self.app.get("/api/torrents")
        async def get_torrents(category: Optional[str] = None):
            try:
                torrents = await self.qbt_client.get_torrents(category)
                return {"success": True, "data": torrents}
            except Exception as e:
                logger.error(f"获取种子列表失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # 获取分类列表
        @self.app.get("/api/categories")
        async def get_categories():
            try:
                categories = await self.qbt_client.get_existing_categories()
                return {"success": True, "data": categories}
            except Exception as e:
                logger.error(f"获取分类列表失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # 暂停种子
        @self.app.post("/api/torrents/{torrent_hash}/pause")
        async def pause_torrent(torrent_hash: str):
            try:
                result = await self.qbt_client.pause_torrent(torrent_hash)
                return {"success": True, "data": result}
            except Exception as e:
                logger.error(f"暂停种子失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # 恢复种子
        @self.app.post("/api/torrents/{torrent_hash}/resume")
        async def resume_torrent(torrent_hash: str):
            try:
                result = await self.qbt_client.resume_torrent(torrent_hash)
                return {"success": True, "data": result}
            except Exception as e:
                logger.error(f"恢复种子失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # 删除种子
        @self.app.delete("/api/torrents/{torrent_hash}")
        async def delete_torrent(torrent_hash: str, delete_files: bool = False):
            try:
                result = await self.qbt_client.delete_torrent(torrent_hash, delete_files)
                return {"success": True, "data": result}
            except Exception as e:
                logger.error(f"删除种子失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # 获取统计信息
        @self.app.get("/api/stats")
        async def get_stats():
            try:
                # 合并所有统计信息
                stats = {
                    "qbt_client": self.qbt_client.get_stats(),
                    "traffic_controller": self.traffic_controller.get_all_stats(),
                    "metrics": self.metrics_collector.get_stats(),
                    "timestamp": datetime.now().isoformat()
                }
                return {"success": True, "data": stats}
            except Exception as e:
                logger.error(f"获取统计信息失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # 工作流API - 获取工作流统计
        @self.app.get("/api/workflow/stats")
        async def get_workflow_stats():
            try:
                from ..workflow_engine import get_workflow_engine
                workflow_engine = get_workflow_engine()

                if not workflow_engine:
                    return {"success": False, "error": "工作流引擎未初始化"}

                stats = workflow_engine.get_stats()
                return {"success": True, "data": stats}
            except Exception as e:
                logger.error(f"获取工作流统计失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # 工作流API - 获取最近执行记录
        @self.app.get("/api/workflow/executions")
        async def get_workflow_executions(limit: int = 10):
            try:
                from ..workflow_engine import get_workflow_engine
                workflow_engine = get_workflow_engine()

                if not workflow_engine:
                    return {"success": False, "error": "工作流引擎未初始化"}

                executions = workflow_engine.get_recent_executions(limit)
                return {"success": True, "data": executions}
            except Exception as e:
                logger.error(f"获取工作流执行记录失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # 工作流API - 导出规则
        @self.app.get("/api/workflow/rules/export")
        async def export_workflow_rules():
            try:
                from ..workflow_engine import get_workflow_engine
                workflow_engine = get_workflow_engine()

                if not workflow_engine:
                    return {"success": False, "error": "工作流引擎未初始化"}

                # 获取规则数据
                rules = []
                for rule in workflow_engine.rule_engine.rules:
                    rules.append({
                        "name": rule.name,
                        "enabled": rule.enabled,
                        "priority": rule.priority,
                        "conditions": rule.conditions,
                        "actions": rule.actions,
                        "description": rule.description
                    })

                return {"success": True, "data": rules}
            except Exception as e:
                logger.error(f"导出工作流规则失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # 工作流API - 导入规则
        @self.app.post("/api/workflow/rules/import")
        async def import_workflow_rules(request: Request):
            try:
                from ..workflow_engine import get_workflow_engine, WorkflowRule
                workflow_engine = get_workflow_engine()

                if not workflow_engine:
                    return {"success": False, "error": "工作流引擎未初始化"}

                data = await request.json()
                rules_data = data.get("rules", [])

                # 导入规则
                for rule_data in rules_data:
                    rule = WorkflowRule(
                        name=rule_data["name"],
                        enabled=rule_data.get("enabled", True),
                        priority=rule_data.get("priority", 0),
                        conditions=rule_data.get("conditions", []),
                        actions=rule_data.get("actions", []),
                        description=rule_data.get("description", "")
                    )
                    workflow_engine.rule_engine.add_rule(rule)

                return {"success": True, "message": f"成功导入 {len(rules_data)} 条规则"}
            except Exception as e:
                logger.error(f"导入工作流规则失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # RSS API - 获取RSS统计
        @self.app.get("/api/rss/stats")
        async def get_rss_stats():
            try:
                from ..rss_manager import get_rss_manager
                rss_manager = get_rss_manager()

                if not rss_manager:
                    return {"success": False, "error": "RSS管理器未初始化"}

                stats = rss_manager.get_stats()
                return {"success": True, "data": stats}
            except Exception as e:
                logger.error(f"获取RSS统计失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # RSS API - 获取RSS源列表
        @self.app.get("/api/rss/sources")
        async def get_rss_sources():
            try:
                from ..rss_manager import get_rss_manager
                rss_manager = get_rss_manager()

                if not rss_manager:
                    return {"success": False, "error": "RSS管理器未初始化"}

                sources = rss_manager.get_all_sources()
                return {
                    "success": True,
                    "data": [
                        {
                            "name": s.name,
                            "url": s.url,
                            "enabled": s.enabled,
                            "check_interval": s.check_interval,
                            "download_enabled": s.download_enabled,
                            "category": s.category,
                            "item_count": len(s.items),
                            "downloaded_count": s.downloaded_count,
                            "skipped_count": s.skipped_count,
                            "error_count": s.error_count,
                            "last_check": s.last_check.isoformat() if s.last_check else None
                        }
                        for s in sources
                    ]
                }
            except Exception as e:
                logger.error(f"获取RSS源失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # RSS API - 添加RSS源
        @self.app.post("/api/rss/sources")
        async def add_rss_source(request: Request):
            try:
                from ..rss_manager import get_rss_manager
                rss_manager = get_rss_manager()

                if not rss_manager:
                    return {"success": False, "error": "RSS管理器未初始化"}

                data = await request.json()
                name = data.get("name")
                url = data.get("url")
                category = data.get("category", "rss")
                check_interval = data.get("check_interval", 1800)
                download_enabled = data.get("download_enabled", True)

                if not name or not url:
                    return {"success": False, "error": "名称和URL不能为空"}

                rss_manager.add_source(
                    name=name,
                    url=url,
                    category=category,
                    check_interval=check_interval,
                    download_enabled=download_enabled
                )

                return {"success": True, "message": "RSS源添加成功"}
            except Exception as e:
                logger.error(f"添加RSS源失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # RSS API - 更新RSS源
        @self.app.put("/api/rss/sources/{source_name}")
        async def update_rss_source(source_name: str, request: Request):
            try:
                from ..rss_manager import get_rss_manager
                rss_manager = get_rss_manager()

                if not rss_manager:
                    return {"success": False, "error": "RSS管理器未初始化"}

                data = await request.json()
                source = rss_manager.get_source(source_name)

                if not source:
                    return {"success": False, "error": "RSS源不存在"}

                # 更新属性
                if "enabled" in data:
                    source.enabled = data["enabled"]
                if "check_interval" in data:
                    source.check_interval = data["check_interval"]
                if "download_enabled" in data:
                    source.download_enabled = data["download_enabled"]
                if "category" in data:
                    source.category = data["category"]

                return {"success": True, "message": "RSS源更新成功"}
            except Exception as e:
                logger.error(f"更新RSS源失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # RSS API - 强制检查所有源
        @self.app.post("/api/rss/check-all")
        async def force_check_rss():
            try:
                from ..rss_manager import get_rss_manager
                rss_manager = get_rss_manager()

                if not rss_manager:
                    return {"success": False, "error": "RSS管理器未初始化"}

                await rss_manager.force_check_all()
                return {"success": True, "message": "检查任务已启动"}
            except Exception as e:
                logger.error(f"强制检查RSS失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # RSS API - 获取最近项目
        @self.app.get("/api/rss/items")
        async def get_rss_items(limit: int = 20):
            try:
                from ..rss_manager import get_rss_manager
                rss_manager = get_rss_manager()

                if not rss_manager:
                    return {"success": False, "error": "RSS管理器未初始化"}

                items = rss_manager.get_recent_items(limit)
                return {"success": True, "data": items}
            except Exception as e:
                logger.error(f"获取RSS项目失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # RSS API - 导出配置
        @self.app.get("/api/rss/config/export")
        async def export_rss_config():
            try:
                from ..rss_manager import get_rss_manager
                rss_manager = get_rss_manager()

                if not rss_manager:
                    return {"success": False, "error": "RSS管理器未初始化"}

                # 生成配置数据
                config = {"sources": []}
                for source in rss_manager.get_all_sources():
                    config["sources"].append({
                        "name": source.name,
                        "url": source.url,
                        "enabled": source.enabled,
                        "check_interval": source.check_interval,
                        "download_enabled": source.download_enabled,
                        "category": source.category,
                        "filters": source.filters
                    })

                return {"success": True, "data": config}
            except Exception as e:
                logger.error(f"导出RSS配置失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # RSS API - 导入配置
        @self.app.post("/api/rss/config/import")
        async def import_rss_config(request: Request):
            try:
                from ..rss_manager import get_rss_manager
                rss_manager = get_rss_manager()

                if not rss_manager:
                    return {"success": False, "error": "RSS管理器未初始化"}

                data = await request.json()
                sources_data = data.get("sources", [])

                for source_data in sources_data:
                    rss_manager.add_source(
                        name=source_data["name"],
                        url=source_data["url"],
                        enabled=source_data.get("enabled", True),
                        check_interval=source_data.get("check_interval", 1800),
                        category=source_data.get("category", "rss"),
                        download_enabled=source_data.get("download_enabled", True),
                        filters=source_data.get("filters", [])
                    )

                return {"success": True, "message": f"成功导入 {len(sources_data)} 个RSS源"}
            except Exception as e:
                logger.error(f"导入RSS配置失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # 获取健康状态
        @self.app.get("/api/health")
        async def get_health():
            try:
                health_results = await self.health_checker.run_all_checks()
                return {
                    "success": True,
                    "data": {
                        "overall": await self.health_checker.get_overall_status().value,
                        "checks": [r.to_dict() for r in health_results]
                    }
                }
            except Exception as e:
                logger.error(f"获取健康状态失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # 获取性能指标
        @self.app.get("/api/metrics")
        async def get_metrics(limit: int = 100):
            try:
                # 这里应该从metrics_collector获取实际的指标数据
                # 暂时返回模拟数据
                return {
                    "success": True,
                    "data": {
                        "requests_total": 1000,
                        "errors_total": 5,
                        "avg_response_time": 150.5,
                        "timestamp": datetime.now().isoformat()
                    }
                }
            except Exception as e:
                logger.error(f"获取性能指标失败: {str(e)}")
                return {"success": False, "error": str(e)}

        # WebSocket端点 - 带输入验证
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self.ws_manager.connect(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    # 处理客户端消息 - 带输入验证
                    try:
                        raw_message = json.loads(data)
                        # 使用Pydantic模型验证消息
                        message = WebSocketMessage(**raw_message)
                        await self._handle_websocket_message(websocket, message)
                    except json.JSONDecodeError:
                        await websocket.send_json(APIResponse.error("Invalid JSON", "JSON_ERROR").model_dump(mode='json'))
                    except ValueError as ve:
                        await websocket.send_json(APIResponse.error(str(ve), "VALIDATION_ERROR").model_dump(mode='json'))
            except WebSocketDisconnect:
                self.ws_manager.disconnect(websocket)

    async def _handle_websocket_message(self, websocket: WebSocket, message: WebSocketMessage):
        """处理WebSocket消息 - 使用类型化的消息模型"""
        message_type = message.type

        if message_type == WebSocketMessageType.PING:
            await websocket.send_json({"type": "pong", "request_id": message.request_id})
        elif message_type == WebSocketMessageType.STATS_REQUEST:
            # 主动推送统计信息
            stats = await self._get_realtime_stats()
            await websocket.send_json({
                "type": "stats_update",
                "data": stats,
                "request_id": message.request_id
            })

    async def _get_realtime_stats(self) -> Dict[str, Any]:
        """获取实时统计信息"""
        try:
            return {
                "qbt_client": self.qbt_client.get_stats(),
                "traffic_controller": self.traffic_controller.get_all_stats(),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"获取实时统计失败: {str(e)}")
            return {"error": str(e)}

    async def start_broadcasting(self):
        """启动WebSocket广播任务"""
        async def broadcast_loop():
            while True:
                try:
                    stats = await self._get_realtime_stats()
                    await self.ws_manager.broadcast({
                        "type": "stats_update",
                        "data": stats
                    })
                    await asyncio.sleep(5)  # 每5秒广播一次
                except Exception as e:
                    logger.error(f"WebSocket广播错误: {str(e)}")
                    await asyncio.sleep(5)

        self._broadcast_task = asyncio.create_task(broadcast_loop())

    async def stop_broadcasting(self):
        """停止WebSocket广播任务"""
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

    def mount_static(self):
        """挂载静态文件和模板"""
        # 挂载静态文件
        self.app.mount(
            "/static",
            StaticFiles(directory="qbittorrent_monitor/web_interface/static"),
            name="static"
        )

        # 配置模板
        self.templates = Jinja2Templates(
            directory="qbittorrent_monitor/web_interface/templates"
        )

    async def start(self, host: str = "0.0.0.0", port: int = 8000):
        """启动Web服务"""
        self.mount_static()
        await self.start_broadcasting()

        config = uvicorn.Config(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )
        server = uvicorn.Server(config)

        logger.info(f"Web管理界面启动: http://{host}:{port}")
        await server.serve()

    async def stop(self):
        """停止Web服务"""
        await self.stop_broadcasting()
        logger.info("Web管理界面已停止")


# 全局Web界面实例
_web_interface: Optional[WebInterface] = None


async def start_web_interface(
    config: AppConfig,
    qbt_client: EnhancedQBittorrentClient,
    host: str = "0.0.0.0",
    port: int = 8000
):
    """启动Web界面"""
    global _web_interface

    if _web_interface:
        logger.warning("Web界面已在运行")
        return _web_interface

    _web_interface = WebInterface(config, qbt_client)
    await _web_interface.start(host, port)

    return _web_interface


async def stop_web_interface():
    """停止Web界面"""
    global _web_interface

    if _web_interface:
        await _web_interface.stop()
        _web_interface = None


def get_web_interface() -> Optional[WebInterface]:
    """获取Web界面实例"""
    return _web_interface
