"""
健康检查模块
提供HTTP健康检查端点，监控系统运行状态
"""

import asyncio
import time
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

from aiohttp import web, ClientSession
import aiohttp_cors

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """健康状态"""
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: datetime
    uptime: float  # 运行时间(秒)
    version: str
    checks: Dict[str, Any]
    metrics: Dict[str, Any]
    errors: List[str]


@dataclass
class ComponentStatus:
    """组件状态"""
    name: str
    status: str  # "healthy", "degraded", "unhealthy", "unknown"
    response_time: Optional[float] = None
    last_check: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None


class HealthChecker:
    """健康检查器"""

    def __init__(self, config, qbt_client=None, ai_classifier=None):
        self.config = config
        self.qbt_client = qbt_client
        self.ai_classifier = ai_classifier
        self.start_time = time.time()

        # 组件状态缓存
        self._component_status: Dict[str, ComponentStatus] = {}
        self._last_full_check = 0
        self._check_interval = 30  # 30秒检查一次

        # 健康检查历史
        self._health_history: List[HealthStatus] = []
        self._max_history = 100

        logger.info("健康检查器初始化完成")

    async def start(self, host: str = "0.0.0.0", port: int = 8090):
        """启动健康检查HTTP服务"""
        app = web.Application()

        # 配置CORS
        cors = aiohttp_cors.setup(app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })

        # 注册路由
        app.router.add_get("/health", self.health_check)
        app.router.add_get("/health/ready", self.readiness_check)
        app.router.add_get("/health/live", self.liveness_check)
        app.router.add_get("/health/components", self.components_check)
        app.router.add_get("/health/metrics", self.metrics_check)
        app.router.add_get("/health/detailed", self.detailed_health_check)

        # 添加CORS到所有路由
        for route in list(app.router.routes()):
            cors.add(route)

        # 启动后台健康检查任务
        asyncio.create_task(self._background_health_check())

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, host, port)
        await site.start()

        logger.info(f"健康检查服务已启动: http://{host}:{port}")
        logger.info("健康检查端点:")
        logger.info(f"  - GET http://{host}:{port}/health - 基本健康检查")
        logger.info(f"  - GET http://{host}:{port}/health/ready - 就绪检查")
        logger.info(f"  - GET http://{host}:{port}/health/live - 存活检查")
        logger.info(f"  - GET http://{host}:{port}/health/components - 组件检查")
        logger.info(f"  - GET http://{host}:{port}/health/metrics - 指标检查")
        logger.info(f"  - GET http://{host}:{port}/health/detailed - 详细检查")

        return runner

    async def _background_health_check(self):
        """后台健康检查任务"""
        while True:
            try:
                await self._update_component_status()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"后台健康检查出错: {e}")
                await asyncio.sleep(10)  # 出错后等待10秒再试

    async def _update_component_status(self):
        """更新所有组件状态"""
        current_time = time.time()

        # 避免频繁检查
        if current_time - self._last_full_check < self._check_interval:
            return

        self._last_full_check = current_time

        # 并发检查所有组件
        tasks = [
            self._check_qbittorrent(),
            self._check_ai_classifier(),
            self._check_filesystem(),
            self._check_memory(),
            self._check_network()
        ]

        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"组件状态检查出错: {e}")

    async def _check_qbittorrent(self) -> ComponentStatus:
        """检查qBittorrent连接"""
        start_time = time.time()
        status = ComponentStatus(
            name="qbittorrent",
            status="unknown",
            last_check=datetime.now(),
            metadata={}
        )

        try:
            if self.qbt_client:
                # 检查连接
                app_version = await self.qbt_client.get_application_version()
                connection_info = await self.qbt_client.get_connection_info()

                status.status = "healthy"
                status.response_time = time.time() - start_time
                status.metadata = {
                    "version": app_version.get("version", "unknown"),
                    "api_version": app_version.get("api_version", "unknown"),
                    "connection_info": connection_info
                }

                logger.debug(f"qBittorrent健康检查通过: {app_version.get('version', 'unknown')}")
            else:
                status.status = "degraded"
                status.error = "qBittorrent客户端未初始化"

        except Exception as e:
            status.status = "unhealthy"
            status.error = str(e)
            logger.warning(f"qBittorrent健康检查失败: {e}")

        self._component_status["qbittorrent"] = status
        return status

    async def _check_ai_classifier(self) -> ComponentStatus:
        """检查AI分类器"""
        start_time = time.time()
        status = ComponentStatus(
            name="ai_classifier",
            status="unknown",
            last_check=datetime.now(),
            metadata={}
        )

        try:
            if self.ai_classifier:
                # 检查AI分类器是否可用
                test_content = "测试内容"
                result = await self.ai_classifier.classify_content(test_content)

                status.status = "healthy"
                status.response_time = time.time() - start_time
                status.metadata = {
                    "provider": getattr(self.ai_classifier, 'provider', 'unknown'),
                    "model": getattr(self.ai_classifier, 'model', 'unknown'),
                    "test_result": result.category if result else None
                }

                logger.debug(f"AI分类器健康检查通过: {result.category if result else 'unknown'}")
            else:
                status.status = "degraded"
                status.error = "AI分类器未初始化"

        except Exception as e:
            status.status = "unhealthy"
            status.error = str(e)
            logger.warning(f"AI分类器健康检查失败: {e}")

        self._component_status["ai_classifier"] = status
        return status

    async def _check_filesystem(self) -> ComponentStatus:
        """检查文件系统"""
        start_time = time.time()
        status = ComponentStatus(
            name="filesystem",
            status="healthy",
            last_check=datetime.now(),
            metadata={}
        )

        try:
            # 检查关键目录
            checks = []

            # 检查日志目录
            log_dir = Path("logs")
            if log_dir.exists():
                checks.append(("logs_dir", True, str(log_dir)))
            else:
                log_dir.mkdir(exist_ok=True)
                checks.append(("logs_dir", True, str(log_dir)))

            # 检查缓存目录
            cache_dir = Path(".cache")
            if cache_dir.exists():
                checks.append(("cache_dir", True, str(cache_dir)))
            else:
                cache_dir.mkdir(exist_ok=True)
                checks.append(("cache_dir", True, str(cache_dir)))

            # 检查磁盘空间
            import shutil
            total, used, free = shutil.disk_usage(".")
            free_percent = (free / total) * 100

            if free_percent < 5:  # 少于5%空间
                status.status = "degraded"
                status.error = f"磁盘空间不足: {free_percent:.1f}%"

            status.response_time = time.time() - start_time
            status.metadata = {
                "disk_total_gb": round(total / (1024**3), 2),
                "disk_used_gb": round(used / (1024**3), 2),
                "disk_free_gb": round(free / (1024**3), 2),
                "disk_free_percent": round(free_percent, 2),
                "directory_checks": checks
            }

        except Exception as e:
            status.status = "unhealthy"
            status.error = str(e)
            logger.warning(f"文件系统健康检查失败: {e}")

        self._component_status["filesystem"] = status
        return status

    async def _check_memory(self) -> ComponentStatus:
        """检查内存使用"""
        start_time = time.time()
        status = ComponentStatus(
            name="memory",
            status="healthy",
            last_check=datetime.now(),
            metadata={}
        )

        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            # 系统内存信息
            system_memory = psutil.virtual_memory()

            status.response_time = time.time() - start_time
            status.metadata = {
                "process_memory_mb": round(memory_info.rss / (1024**2), 2),
                "process_memory_percent": round(memory_percent, 2),
                "system_memory_total_gb": round(system_memory.total / (1024**3), 2),
                "system_memory_available_gb": round(system_memory.available / (1024**3), 2),
                "system_memory_percent": system_memory.percent
            }

            # 内存使用过高警告
            if memory_percent > 80:
                status.status = "degraded"
                status.error = f"进程内存使用过高: {memory_percent:.1f}%"

        except ImportError:
            # psutil未安装
            status.status = "degraded"
            status.error = "psutil未安装，无法检查内存"
        except Exception as e:
            status.status = "unhealthy"
            status.error = str(e)

        self._component_status["memory"] = status
        return status

    async def _check_network(self) -> ComponentStatus:
        """检查网络连接"""
        start_time = time.time()
        status = ComponentStatus(
            name="network",
            status="healthy",
            last_check=datetime.now(),
            metadata={}
        )

        try:
            async with ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                # 检查外网连接
                test_urls = [
                    "https://httpbin.org/get",
                    "https://api.github.com",
                ]

                successful_checks = []
                failed_checks = []

                for url in test_urls:
                    try:
                        async with session.get(url) as response:
                            if response.status == 200:
                                successful_checks.append(url)
                            else:
                                failed_checks.append(f"{url} (status: {response.status})")
                    except Exception as e:
                        failed_checks.append(f"{url} (error: {str(e)[:50]})")

                status.response_time = time.time() - start_time
                status.metadata = {
                    "successful_checks": successful_checks,
                    "failed_checks": failed_checks,
                    "success_rate": len(successful_checks) / len(test_urls) * 100
                }

                if len(successful_checks) == 0:
                    status.status = "unhealthy"
                    status.error = "所有网络连接测试失败"
                elif len(failed_checks) > 0:
                    status.status = "degraded"
                    status.error = f"部分网络连接失败: {len(failed_checks)}/{len(test_urls)}"

        except Exception as e:
            status.status = "unhealthy"
            status.error = str(e)

        self._component_status["network"] = status
        return status

    def _calculate_overall_status(self) -> str:
        """计算整体健康状态"""
        if not self._component_status:
            return "unknown"

        statuses = [comp.status for comp in self._component_status.values()]

        if all(s == "healthy" for s in statuses):
            return "healthy"
        elif any(s == "unhealthy" for s in statuses):
            return "unhealthy"
        elif any(s == "degraded" for s in statuses):
            return "degraded"
        else:
            return "unknown"

    async def get_health_status(self) -> HealthStatus:
        """获取健康状态"""
        await self._update_component_status()

        overall_status = self._calculate_overall_status()
        uptime = time.time() - self.start_time

        # 收集错误信息
        errors = []
        for component, status in self._component_status.items():
            if status.error:
                errors.append(f"{component}: {status.error}")

        # 收集指标
        metrics = {
            "uptime_seconds": uptime,
            "component_count": len(self._component_status),
            "healthy_components": sum(1 for s in self._component_status.values() if s.status == "healthy"),
            "degraded_components": sum(1 for s in self._component_status.values() if s.status == "degraded"),
            "unhealthy_components": sum(1 for s in self._component_status.values() if s.status == "unhealthy"),
            "timestamp": datetime.now().isoformat()
        }

        health_status = HealthStatus(
            status=overall_status,
            timestamp=datetime.now(),
            uptime=uptime,
            version="2.4.0",  # 从配置或常量获取
            checks={name: asdict(status) for name, status in self._component_status.items()},
            metrics=metrics,
            errors=errors
        )

        # 保存到历史记录
        self._health_history.append(health_status)
        if len(self._health_history) > self._max_history:
            self._health_history.pop(0)

        return health_status

    # HTTP处理函数
    async def health_check(self, request: web.Request) -> web.Response:
        """基本健康检查"""
        try:
            status = await self.get_health_status()
            return web.json_response({
                "status": status.status,
                "timestamp": status.timestamp.isoformat(),
                "uptime": status.uptime
            }, status=200 if status.status == "healthy" else 503)
        except Exception as e:
            return web.json_response({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)

    async def readiness_check(self, request: web.Request) -> web.Response:
        """就绪检查"""
        try:
            status = await self.get_health_status()
            is_ready = status.status != "unhealthy"

            return web.json_response({
                "ready": is_ready,
                "status": status.status,
                "components": {name: comp.status for name, comp in status.checks.items()}
            }, status=200 if is_ready else 503)
        except Exception as e:
            return web.json_response({
                "ready": False,
                "error": str(e)
            }, status=500)

    async def liveness_check(self, request: web.Request) -> web.Response:
        """存活检查"""
        # 存活检查应该轻量级，只检查进程是否还活着
        return web.json_response({
            "alive": True,
            "timestamp": datetime.now().isoformat(),
            "uptime": time.time() - self.start_time
        })

    async def components_check(self, request: web.Request) -> web.Response:
        """组件检查"""
        try:
            status = await self.get_health_status()
            components = {}

            for name, comp_status in status.checks.items():
                components[name] = {
                    "status": comp_status["status"],
                    "last_check": comp_status["last_check"],
                    "response_time": comp_status["response_time"],
                    "error": comp_status["error"]
                }

            return web.json_response({
                "overall_status": status.status,
                "components": components,
                "timestamp": status.timestamp.isoformat()
            })
        except Exception as e:
            return web.json_response({
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)

    async def metrics_check(self, request: web.Request) -> web.Response:
        """指标检查"""
        try:
            status = await self.get_health_status()
            return web.json_response({
                "metrics": status.metrics,
                "timestamp": status.timestamp.isoformat()
            })
        except Exception as e:
            return web.json_response({
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)

    async def detailed_health_check(self, request: web.Request) -> web.Response:
        """详细健康检查"""
        try:
            status = await self.get_health_status()

            # 添加历史数据
            recent_history = self._health_history[-10:] if self._health_history else []

            return web.json_response({
                "status": status.status,
                "timestamp": status.timestamp.isoformat(),
                "uptime": status.uptime,
                "version": status.version,
                "checks": status.checks,
                "metrics": status.metrics,
                "errors": status.errors,
                "recent_history": [
                    {
                        "timestamp": h.timestamp.isoformat(),
                        "status": h.status,
                        "uptime": h.uptime
                    } for h in recent_history
                ]
            })
        except Exception as e:
            return web.json_response({
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }, status=500)