"""Prometheus 指标服务器

提供 HTTP 端点供 Prometheus 抓取指标数据。
"""

import asyncio
import logging
from typing import Optional
from urllib.parse import urlparse

from .metrics import (
    get_metrics_collector,
    init_metrics,
    MetricsCollector,
    CONTENT_TYPE_LATEST,
)

logger = logging.getLogger(__name__)


class MetricsServer:
    """Prometheus 指标 HTTP 服务器
    
    提供 /metrics 端点供 Prometheus 抓取指标。
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9090,
        path: str = "/metrics",
        enabled: bool = True,
    ):
        """初始化指标服务器
        
        Args:
            host: 监听地址
            port: 监听端口
            path: 指标端点路径
            enabled: 是否启用服务器
        """
        self.host = host
        self.port = port
        self.path = path
        self.enabled = enabled
        
        self._server: Optional[asyncio.AbstractServer] = None
        self._running = False
        self._metrics_collector: Optional[MetricsCollector] = None
    
    async def start(self) -> None:
        """启动指标服务器"""
        if not self.enabled:
            logger.info("Prometheus 指标服务器已禁用")
            return
        
        # 初始化指标收集器
        self._metrics_collector = init_metrics(enabled=True)
        
        try:
            self._server = await asyncio.start_server(
                self._handle_request,
                self.host,
                self.port,
            )
            self._running = True
            
            addr = self._server.sockets[0].getsockname()
            logger.info(f"Prometheus 指标服务器已启动: http://{addr[0]}:{addr[1]}{self.path}")
            
        except Exception as e:
            logger.error(f"启动 Prometheus 指标服务器失败: {e}")
            raise
    
    async def stop(self) -> None:
        """停止指标服务器"""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            self._running = False
            logger.info("Prometheus 指标服务器已停止")
    
    async def _handle_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """处理 HTTP 请求
        
        Args:
            reader: 流读取器
            writer: 流写入器
        """
        try:
            # 读取请求行
            request_line = await reader.readline()
            request_line = request_line.decode("utf-8").strip()
            
            # 解析请求
            method, path, _ = self._parse_request_line(request_line)
            
            # 读取并丢弃请求头
            while True:
                line = await reader.readline()
                if line == b"\r\n" or not line:
                    break
            
            # 处理请求
            if method == "GET" and path == self.path:
                await self._send_metrics_response(writer)
            elif method == "GET" and path == "/health":
                await self._send_health_response(writer)
            elif method == "GET" and path == "/":
                await self._send_index_response(writer)
            else:
                await self._send_404_response(writer)
                
        except Exception as e:
            logger.error(f"处理指标请求失败: {e}")
            await self._send_error_response(writer)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
    
    def _parse_request_line(self, request_line: str) -> tuple:
        """解析 HTTP 请求行
        
        Args:
            request_line: 请求行字符串
            
        Returns:
            (method, path, version) 元组
        """
        parts = request_line.split()
        if len(parts) >= 2:
            method = parts[0]
            path = parts[1]
            version = parts[2] if len(parts) > 2 else "HTTP/1.1"
        else:
            method = "GET"
            path = "/"
            version = "HTTP/1.1"
        return method, path, version
    
    async def _send_metrics_response(self, writer: asyncio.StreamWriter) -> None:
        """发送指标响应
        
        Args:
            writer: 流写入器
        """
        collector = self._metrics_collector or get_metrics_collector()
        
        if collector:
            body = collector.generate_latest()
            content_type = collector.content_type()
        else:
            body = b"# No metrics available\n"
            content_type = "text/plain; charset=utf-8"
        
        header = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("utf-8")
        
        writer.write(header)
        writer.write(body)
        await writer.drain()
    
    async def _send_health_response(self, writer: asyncio.StreamWriter) -> None:
        """发送健康检查响应
        
        Args:
            writer: 流写入器
        """
        body = b'{"status": "healthy"}'
        header = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("utf-8")
        
        writer.write(header)
        writer.write(body)
        await writer.drain()
    
    async def _send_index_response(self, writer: asyncio.StreamWriter) -> None:
        """发送索引页响应
        
        Args:
            writer: 流写入器
        """
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>qBittorrent Monitor Metrics</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{ color: #333; }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        a {{
            color: #0066cc;
            text-decoration: none;
        }}
        a:hover {{ text-decoration: underline; }}
        code {{
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
    </style>
</head>
<body>
    <h1>🔍 qBittorrent Clipboard Monitor Metrics</h1>
    <div class="card">
        <h2>Available Endpoints</h2>
        <ul>
            <li><a href="{self.path}">{self.path}</a> - Prometheus metrics endpoint</li>
            <li><a href="/health">/health</a> - Health check endpoint</li>
        </ul>
    </div>
    <div class="card">
        <h2>Prometheus Configuration</h2>
        <p>Add the following to your <code>prometheus.yml</code>:</p>
        <pre><code>scrape_configs:
  - job_name: 'qbittorrent-monitor'
    static_configs:
      - targets: ['localhost:{self.port}']
    scrape_interval: 15s</code></pre>
    </div>
</body>
</html>"""
        body = html.encode("utf-8")
        header = (
            f"HTTP/1.1 200 OK\r\n"
            f"Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("utf-8")
        
        writer.write(header)
        writer.write(body)
        await writer.drain()
    
    async def _send_404_response(self, writer: asyncio.StreamWriter) -> None:
        """发送 404 响应
        
        Args:
            writer: 流写入器
        """
        body = b"404 Not Found"
        header = (
            f"HTTP/1.1 404 Not Found\r\n"
            f"Content-Type: text/plain\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("utf-8")
        
        writer.write(header)
        writer.write(body)
        await writer.drain()
    
    async def _send_error_response(self, writer: asyncio.StreamWriter) -> None:
        """发送错误响应
        
        Args:
            writer: 流写入器
        """
        body = b"500 Internal Server Error"
        header = (
            f"HTTP/1.1 500 Internal Server Error\r\n"
            f"Content-Type: text/plain\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("utf-8")
        
        writer.write(header)
        writer.write(body)
        await writer.drain()
    
    @property
    def running(self) -> bool:
        """服务器是否正在运行"""
        return self._running
    
    def get_url(self) -> str:
        """获取指标端点 URL
        
        Returns:
            完整的指标端点 URL
        """
        return f"http://{self.host}:{self.port}{self.path}"


class MetricsConfig:
    """指标配置类
    
    用于从配置文件中加载指标相关配置。
    """
    
    def __init__(
        self,
        enabled: bool = True,
        host: str = "0.0.0.0",
        port: int = 9090,
        path: str = "/metrics",
    ):
        """初始化指标配置
        
        Args:
            enabled: 是否启用指标
            host: 监听地址
            port: 监听端口
            path: 指标端点路径
        """
        self.enabled = enabled
        self.host = host
        self.port = port
        self.path = path
    
    @classmethod
    def from_dict(cls, data: dict) -> "MetricsConfig":
        """从字典创建配置
        
        Args:
            data: 配置字典
            
        Returns:
            MetricsConfig 实例
        """
        return cls(
            enabled=data.get("enabled", True),
            host=data.get("host", "0.0.0.0"),
            port=data.get("port", 9090),
            path=data.get("path", "/metrics"),
        )
    
    def to_dict(self) -> dict:
        """转换为字典
        
        Returns:
            配置字典
        """
        return {
            "enabled": self.enabled,
            "host": self.host,
            "port": self.port,
            "path": self.path,
        }


async def start_metrics_server(
    host: str = "0.0.0.0",
    port: int = 9090,
    path: str = "/metrics",
    enabled: bool = True,
) -> Optional[MetricsServer]:
    """启动指标服务器（便捷函数）
    
    Args:
        host: 监听地址
        port: 监听端口
        path: 指标端点路径
        enabled: 是否启用
        
    Returns:
        MetricsServer 实例，如果禁用则返回 None
    """
    if not enabled:
        logger.info("Prometheus 指标服务器已禁用")
        return None
    
    server = MetricsServer(
        host=host,
        port=port,
        path=path,
        enabled=enabled,
    )
    await server.start()
    return server
