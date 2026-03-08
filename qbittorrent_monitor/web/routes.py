"""路由定义"""

from typing import Optional

from fastapi import APIRouter, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .app import get_web_monitor, WebMonitor

router = APIRouter()


# ===== 请求模型 =====

class AddTorrentRequest(BaseModel):
    magnet: str
    category: Optional[str] = None


class UpdateCategoryRequest(BaseModel):
    save_path: str
    keywords: list


class UpdateConfigRequest(BaseModel):
    qbittorrent: Optional[dict] = None
    ai: Optional[dict] = None
    check_interval: Optional[float] = None
    log_level: Optional[str] = None


# ===== 页面路由 =====

def register_routes(app: FastAPI, templates: Jinja2Templates):
    """注册所有路由"""
    
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """主页/仪表盘"""
        monitor = get_web_monitor()
        stats = monitor.get_stats() if monitor else {}
        
        return templates.TemplateResponse("index.html", {
            "request": request,
            "stats": stats,
            "is_running": monitor.is_running if monitor else False
        })
    
    @app.get("/history", response_class=HTMLResponse)
    async def history_page(request: Request):
        """历史记录页面"""
        return templates.TemplateResponse("history.html", {"request": request})
    
    @app.get("/categories", response_class=HTMLResponse)
    async def categories_page(request: Request):
        """分类管理页面"""
        monitor = get_web_monitor()
        categories = monitor.get_categories() if monitor else {}
        
        return templates.TemplateResponse("categories.html", {
            "request": request,
            "categories": categories
        })
    
    @app.get("/config", response_class=HTMLResponse)
    async def config_page(request: Request):
        """配置页面"""
        monitor = get_web_monitor()
        config = monitor._get_safe_config() if monitor else {}
        
        return templates.TemplateResponse("config.html", {
            "request": request,
            "config": config
        })
    
    @app.get("/logs", response_class=HTMLResponse)
    async def logs_page(request: Request):
        """日志页面"""
        return templates.TemplateResponse("logs.html", {"request": request})
    
    # ===== API 路由 =====
    
    @app.get("/api/stats")
    async def get_stats():
        """获取统计信息"""
        monitor = get_web_monitor()
        if not monitor:
            return JSONResponse(
                status_code=503,
                content={"error": "服务不可用"}
            )
        
        return monitor.get_stats()
    
    @app.post("/api/torrents")
    async def add_torrent(request: AddTorrentRequest):
        """手动添加磁力链接"""
        monitor = get_web_monitor()
        if not monitor:
            return JSONResponse(
                status_code=503,
                content={"error": "服务不可用"}
            )
        
        result = await monitor.add_magnet(request.magnet, request.category)
        
        if result.get("success"):
            return result
        else:
            return JSONResponse(
                status_code=400,
                content=result
            )
    
    @app.get("/api/categories")
    async def get_categories():
        """获取分类列表"""
        monitor = get_web_monitor()
        if not monitor:
            return JSONResponse(
                status_code=503,
                content={"error": "服务不可用"}
            )
        
        return monitor.get_categories()
    
    @app.post("/api/categories/{name}")
    async def update_category(name: str, request: UpdateCategoryRequest):
        """更新分类"""
        monitor = get_web_monitor()
        if not monitor:
            return JSONResponse(
                status_code=503,
                content={"error": "服务不可用"}
            )
        
        success = monitor.update_category(name, request.save_path, request.keywords)
        
        if success:
            return {"success": True, "message": f"分类 '{name}' 已更新"}
        else:
            return JSONResponse(
                status_code=400,
                content={"error": "更新失败"}
            )
    
    @app.delete("/api/categories/{name}")
    async def delete_category(name: str):
        """删除分类"""
        monitor = get_web_monitor()
        if not monitor:
            return JSONResponse(
                status_code=503,
                content={"error": "服务不可用"}
            )
        
        success = monitor.delete_category(name)
        
        if success:
            return {"success": True, "message": f"分类 '{name}' 已删除"}
        else:
            return JSONResponse(
                status_code=404,
                content={"error": "分类不存在"}
            )
    
    @app.get("/api/history")
    async def get_history(limit: int = 100, offset: int = 0):
        """获取历史记录"""
        monitor = get_web_monitor()
        if not monitor:
            return JSONResponse(
                status_code=503,
                content={"error": "服务不可用"}
            )
        
        return {
            "items": monitor.get_history(limit, offset),
            "total": len(monitor.history),
            "limit": limit,
            "offset": offset
        }
    
    @app.get("/api/config")
    async def get_config():
        """获取配置"""
        monitor = get_web_monitor()
        if not monitor:
            return JSONResponse(
                status_code=503,
                content={"error": "服务不可用"}
            )
        
        return monitor._get_safe_config()
    
    @app.post("/api/config")
    async def update_config(request: UpdateConfigRequest):
        """更新配置"""
        monitor = get_web_monitor()
        if not monitor:
            return JSONResponse(
                status_code=503,
                content={"error": "服务不可用"}
            )
        
        updates = request.dict(exclude_unset=True)
        success = monitor.update_config(updates)
        
        if success:
            return {"success": True, "message": "配置已更新"}
        else:
            return JSONResponse(
                status_code=400,
                content={"error": "更新失败"}
            )
    
    @app.get("/api/logs")
    async def get_logs(limit: int = 100):
        """获取日志"""
        monitor = get_web_monitor()
        if not monitor:
            return JSONResponse(
                status_code=503,
                content={"error": "服务不可用"}
            )
        
        logs = monitor.recent_logs[-limit:] if monitor.recent_logs else []
        
        return {
            "logs": [
                {
                    "timestamp": log.timestamp,
                    "level": log.level,
                    "message": log.message,
                    "source": log.source
                }
                for log in reversed(logs)
            ]
        }
    
    @app.post("/api/control/start")
    async def start_monitor():
        """启动监控"""
        monitor = get_web_monitor()
        if not monitor:
            return JSONResponse(
                status_code=503,
                content={"error": "服务不可用"}
            )
        
        success, message = await monitor.start_monitor()
        
        if success:
            return {"success": True, "message": message}
        else:
            return JSONResponse(
                status_code=400,
                content={"error": message}
            )
    
    @app.post("/api/control/stop")
    async def stop_monitor():
        """停止监控"""
        monitor = get_web_monitor()
        if not monitor:
            return JSONResponse(
                status_code=503,
                content={"error": "服务不可用"}
            )
        
        success, message = await monitor.stop_monitor()
        
        if success:
            return {"success": True, "message": message}
        else:
            return JSONResponse(
                status_code=400,
                content={"error": message}
            )
    
    @app.get("/api/status")
    async def get_status():
        """获取运行状态"""
        monitor = get_web_monitor()
        if not monitor:
            return JSONResponse(
                status_code=503,
                content={"error": "服务不可用"}
            )
        
        return {
            "is_running": monitor.is_running,
            "stats": monitor.get_stats()
        }
    
    # ===== WebSocket 路由 =====
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket 连接"""
        monitor = get_web_monitor()
        if not monitor:
            await websocket.close(code=1011, reason="服务不可用")
            return
        
        await monitor.connect(websocket)
        
        try:
            while True:
                # 接收客户端消息
                data = await websocket.receive_json()
                
                # 处理命令
                if data.get("action") == "get_logs":
                    # 发送最近的日志
                    logs = monitor.recent_logs[-50:] if monitor.recent_logs else []
                    await websocket.send_json({
                        "type": "logs",
                        "data": [
                            {
                                "timestamp": log.timestamp,
                                "level": log.level,
                                "message": log.message,
                                "source": log.source
                            }
                            for log in reversed(logs)
                        ]
                    })
                elif data.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
        except WebSocketDisconnect:
            monitor.disconnect(websocket)
        except Exception as e:
            monitor.disconnect(websocket)
