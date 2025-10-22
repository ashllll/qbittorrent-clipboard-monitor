"""
性能监控仪表板Web应用
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn
import websockets
from collections import defaultdict, deque

# 导入项目模块
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from qbittorrent_monitor.performance_monitor import get_global_monitor
from qbittorrent_monitor.config import ConfigManager

app = FastAPI(
    title="qBittorrent 性能监控仪表板",
    description="实时性能监控和分析仪表板",
    version="1.0.0"
)

# 设置静态文件和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 全局状态管理
class DashboardState:
    def __init__(self):
        self.connected_clients: List[WebSocket] = []
        self.performance_data = deque(maxlen=1000)  # 最近1000个数据点
        self.alerts = deque(maxlen=100)  # 最近100个告警
        self.system_info = {}

    async def add_client(self, websocket: WebSocket):
        self.connected_clients.append(websocket)

    async def remove_client(self, websocket: WebSocket):
        if websocket in self.connected_clients:
            self.connected_clients.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接的客户端"""
        if not self.connected_clients:
            return

        disconnected = []
        for client in self.connected_clients:
            try:
                await client.send_text(json.dumps(message))
            except Exception:
                disconnected.append(client)

        # 清理断开的客户端
        for client in disconnected:
            await self.remove_client(client)

    def add_performance_data(self, data: Dict[str, Any]):
        """添加性能数据"""
        timestamp = datetime.now().isoformat()
        data_point = {
            'timestamp': timestamp,
            **data
        }
        self.performance_data.append(data_point)

    def add_alert(self, alert: Dict[str, Any]):
        """添加告警"""
        alert['timestamp'] = datetime.now().isoformat()
        self.alerts.append(alert)

# 全局状态实例
dashboard_state = DashboardState()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """仪表板主页"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "qBittorrent 性能监控"
    })

@app.get("/api/stats")
async def get_current_stats():
    """获取当前性能统计"""
    try:
        monitor = get_global_monitor()
        if not monitor:
            return {"error": "性能监控器未运行"}

        current_stats = monitor.get_current_stats()
        return {
            "status": "success",
            "data": current_stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": f"获取统计失败: {str(e)}"}

@app.get("/api/history")
async def get_performance_history(minutes: int = 60):
    """获取性能历史数据"""
    try:
        # 从全局状态获取数据
        cutoff_time = datetime.now() - timedelta(minutes=minutes)

        filtered_data = []
        for data_point in dashboard_state.performance_data:
            data_time = datetime.fromisoformat(data_point['timestamp'])
            if data_time >= cutoff_time:
                filtered_data.append(data_point)

        return {
            "status": "success",
            "data": filtered_data,
            "count": len(filtered_data)
        }
    except Exception as e:
        return {"error": f"获取历史数据失败: {str(e)}"}

@app.get("/api/metrics")
async def get_metrics_summary():
    """获取指标摘要"""
    try:
        monitor = get_global_monitor()
        if not monitor:
            return {"error": "性能监控器未运行"}

        # 计算各种指标摘要
        if not dashboard_state.performance_data:
            return {"status": "success", "data": {}}

        # CPU使用率统计
        cpu_values = [dp.get('cpu_percent', 0) for dp in dashboard_state.performance_data if 'cpu_percent' in dp]
        memory_values = [dp.get('memory_percent', 0) for dp in dashboard_state.performance_data if 'memory_percent' in dp]

        summary = {
            "cpu": {
                "current": cpu_values[-1] if cpu_values else 0,
                "average": sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                "max": max(cpu_values) if cpu_values else 0,
                "min": min(cpu_values) if cpu_values else 0
            },
            "memory": {
                "current": memory_values[-1] if memory_values else 0,
                "average": sum(memory_values) / len(memory_values) if memory_values else 0,
                "max": max(memory_values) if memory_values else 0,
                "min": min(memory_values) if memory_values else 0
            },
            "data_points": len(dashboard_state.performance_data),
            "alerts_count": len(dashboard_state.alerts)
        }

        return {"status": "success", "data": summary}
    except Exception as e:
        return {"error": f"获取指标摘要失败: {str(e)}"}

@app.get("/api/alerts")
async def get_alerts():
    """获取告警列表"""
    return {
        "status": "success",
        "data": list(dashboard_state.alerts),
        "count": len(dashboard_state.alerts)
    }

@app.get("/api/system")
async def get_system_info():
    """获取系统信息"""
    try:
        import psutil
        import platform

        system_info = {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "disk_usage": {
                path.disk_usage('/').percent if hasattr(path, 'disk_usage') else 0
                for path in [Path('/')] if hasattr(Path, 'disk_usage')
            },
            "timestamp": datetime.now().isoformat()
        }

        return {"status": "success", "data": system_info}
    except Exception as e:
        return {"error": f"获取系统信息失败: {str(e)}"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接用于实时数据更新"""
    await websocket.accept()
    await dashboard_state.add_client(websocket)

    try:
        while True:
            # 等待客户端消息（保持连接）
            await websocket.receive_text()
    except WebSocketDisconnect:
        await dashboard_state.remove_client(websocket)
    except Exception as e:
        print(f"WebSocket错误: {e}")
        await dashboard_state.remove_client(websocket)

# 后台任务：收集性能数据并广播
async def performance_data_collector():
    """后台性能数据收集任务"""
    while True:
        try:
            monitor = get_global_monitor()
            if monitor:
                current_stats = monitor.get_current_stats()
                dashboard_state.add_performance_data(current_stats)

                # 检查告警条件
                await check_alerts(current_stats)

                # 广播最新数据给连接的客户端
                message = {
                    "type": "performance_update",
                    "data": current_stats,
                    "timestamp": datetime.now().isoformat()
                }
                await dashboard_state.broadcast(message)

        except Exception as e:
            print(f"性能数据收集错误: {e}")

        await asyncio.sleep(5)  # 每5秒收集一次

async def check_alerts(stats: Dict[str, Any]):
    """检查告警条件"""
    alerts = []

    # CPU使用率告警
    cpu_percent = stats.get('cpu_percent', 0)
    if cpu_percent > 90:
        alerts.append({
            "type": "cpu_high",
            "level": "warning",
            "message": f"CPU使用率过高: {cpu_percent:.1f}%",
            "value": cpu_percent
        })
    elif cpu_percent > 95:
        alerts.append({
            "type": "cpu_critical",
            "level": "critical",
            "message": f"CPU使用率严重过高: {cpu_percent:.1f}%",
            "value": cpu_percent
        })

    # 内存使用率告警
    memory_percent = stats.get('memory_percent', 0)
    if memory_percent > 85:
        alerts.append({
            "type": "memory_high",
            "level": "warning",
            "message": f"内存使用率过高: {memory_percent:.1f}%",
            "value": memory_percent
        })
    elif memory_percent > 95:
        alerts.append({
            "type": "memory_critical",
            "level": "critical",
            "message": f"内存使用率严重过高: {memory_percent:.1f}%",
            "value": memory_percent
        })

    # 添加告警到状态
    for alert in alerts:
        dashboard_state.add_alert(alert)

        # 广播告警
        message = {
            "type": "alert",
            "data": alert,
            "timestamp": datetime.now().isoformat()
        }
        await dashboard_state.broadcast(message)

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    # 启动后台数据收集任务
    asyncio.create_task(performance_data_collector())

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    # 清理WebSocket连接
    for client in dashboard_state.connected_clients:
        await client.close()

def main():
    """启动仪表板应用"""
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8081,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()