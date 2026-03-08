"""Web 管理界面模块

提供基于 FastAPI + Jinja2 的 Web 管理界面，支持：
- 仪表盘显示统计信息
- 实时监控剪贴板活动
- 手动添加磁力链接
- 分类规则管理
- 配置管理
- 历史记录查看
"""

from .app import create_app, WebMonitor, run_web_server

__all__ = ["create_app", "WebMonitor", "run_web_server"]
