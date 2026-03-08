"""CLI 用户界面组件 - 提供丰富的交互体验

此模块提供丰富的命令行交互组件，包括彩色输出、表格展示、
进度指示等，显著提升用户体验。

依赖:
    rich: ^13.0

示例:
    >>> from qbittorrent_monitor.cli_ui import console, StyledOutput
    >>> StyledOutput.success("操作成功！")
    ✓ 操作成功！
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import timedelta

# Rich 库导入
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.progress import (
        Progress, 
        SpinnerColumn, 
        TextColumn, 
        BarColumn, 
        TaskProgressColumn,
        TimeElapsedColumn
    )
    from rich.syntax import Syntax
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

import json
import logging

logger = logging.getLogger(__name__)

# 全局 console 实例
if RICH_AVAILABLE:
    console = Console()
else:
    # Fallback: 使用标准输出
    class FakeConsole:
        def print(self, *args, **kwargs):
            print(*args)
    console = FakeConsole()


class StyledOutput:
    """样式化输出工具类
    
    提供统一的成功、错误、警告、信息消息输出格式。
    当 rich 不可用时，自动降级为标准文本输出。
    """
    
    # 颜色主题
    COLORS = {
        "primary": "cyan",
        "success": "green",
        "warning": "yellow",
        "error": "red",
        "info": "blue",
        "muted": "dim",
        "highlight": "magenta",
    }
    
    @classmethod
    def banner(
        cls, 
        title: str, 
        version: str, 
        description: str = "",
        subtitle: str = ""
    ) -> None:
        """显示应用启动横幅
        
        Args:
            title: 应用标题
            version: 版本号
            description: 应用描述
            subtitle: 副标题
        """
        if not RICH_AVAILABLE:
            print(f"{'='*50}")
            print(f"{title} v{version}")
            if description:
                print(description)
            print(f"{'='*50}")
            return
        
        content = Text()
        content.append(f"{title}\n", style=f"bold {cls.COLORS['primary']}")
        content.append(f"版本: {version}", style=cls.COLORS["muted"])
        if description:
            content.append(f"\n{description}", style=cls.COLORS["info"])
        if subtitle:
            content.append(f"\n{subtitle}", style=cls.COLORS["muted"])
        
        console.print(Panel(
            content,
            box=box.ROUNDED,
            border_style=cls.COLORS["primary"],
            padding=(1, 2)
        ))
    
    @classmethod
    def success(cls, message: str) -> None:
        """成功消息"""
        if RICH_AVAILABLE:
            console.print(f"[{cls.COLORS['success']}✓[/] {message}")
        else:
            print(f"✓ {message}")
    
    @classmethod
    def error(cls, message: str) -> None:
        """错误消息"""
        if RICH_AVAILABLE:
            console.print(f"[{cls.COLORS['error']}✗[/] {message}")
        else:
            print(f"✗ {message}")
    
    @classmethod
    def warning(cls, message: str) -> None:
        """警告消息"""
        if RICH_AVAILABLE:
            console.print(f"[{cls.COLORS['warning']}⚠[/] {message}")
        else:
            print(f"⚠ {message}")
    
    @classmethod
    def info(cls, message: str) -> None:
        """信息消息"""
        if RICH_AVAILABLE:
            console.print(f"[{cls.COLORS['info']}ℹ[/] {message}")
        else:
            print(f"ℹ {message}")
    
    @classmethod
    def magnet_added(
        cls, 
        name: str, 
        category: str, 
        size: str = "",
        method: str = ""
    ) -> None:
        """磁力链接添加成功提示
        
        Args:
            name: 磁力链接名称
            category: 分类
            size: 文件大小（可选）
            method: 分类方法（可选）
        """
        size_info = f" [dim]({size})[/]" if size and RICH_AVAILABLE else f" ({size})" if size else ""
        method_info = ""
        if method:
            method_emoji = {"ai": "🤖", "rule": "📋", "fallback": "❓"}.get(method, "")
            method_info = f" [{method_emoji} {method}]" if RICH_AVAILABLE else f" [{method}]"
        
        if RICH_AVAILABLE:
            console.print(
                f"[{cls.COLORS['success']}✓[/] 已添加到 [{cls.COLORS['highlight']}]{category}[/]: "
                f"[bold]{name[:50]}{'...' if len(name) > 50 else ''}[/]{size_info}{method_info}"
            )
        else:
            print(f"✓ 已添加到 [{category}]: {name[:50]}{'...' if len(name) > 50 else ''}{size_info}{method_info}")
    
    @classmethod
    def config_info(cls, config_dict: Dict[str, Any]) -> None:
        """以美观格式显示配置信息
        
        Args:
            config_dict: 配置项字典
        """
        if not RICH_AVAILABLE:
            for key, value in config_dict.items():
                print(f"  {key}: {cls._mask_sensitive(key, str(value))}")
            return
        
        table = Table(
            title="[bold]配置信息[/]",
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style=f"bold {cls.COLORS['primary']}"
        )
        table.add_column("配置项", style=cls.COLORS["info"])
        table.add_column("值", style="white")
        
        for key, value in config_dict.items():
            display_value = cls._mask_sensitive(key, str(value))
            table.add_row(key, display_value)
        
        console.print(table)
    
    @staticmethod
    def _mask_sensitive(key: str, value: str) -> str:
        """脱敏敏感信息
        
        Args:
            key: 配置项名称
            value: 配置项值
            
        Returns:
            脱敏后的值
        """
        sensitive_keys = ['password', 'token', 'api_key', 'secret', 'key']
        if any(sk in key.lower() for sk in sensitive_keys):
            if len(value) > 8:
                return value[:4] + "****" + value[-4:]
            return "****"
        return value


class StatsDisplay:
    """统计信息展示"""
    
    @classmethod
    def show_monitor_stats(cls, stats: Dict[str, Any]) -> None:
        """显示监控统计信息表格
        
        Args:
            stats: 统计信息字典
        """
        if not RICH_AVAILABLE:
            print("\n--- 监控统计 ---")
            for key, value in stats.items():
                if not key.startswith('_'):
                    print(f"  {key}: {value}")
            return
        
        table = Table(
            title="[bold cyan]监控统计信息[/]",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )
        table.add_column("指标", style="cyan", no_wrap=True)
        table.add_column("数值", style="green", justify="right")
        table.add_column("说明", style="dim")
        
        # 运行时间
        uptime = stats.get("uptime_seconds", 0)
        uptime_str = str(timedelta(seconds=int(uptime)))
        table.add_row("运行时间", uptime_str, "监控器运行时长")
        
        # 处理统计
        table.add_row(
            "总处理数", 
            str(stats.get("total_processed", 0)),
            "检测到的磁力链接总数"
        )
        table.add_row(
            "成功添加", 
            f"[green]{stats.get('successful_adds', 0)}[/]",
            "成功添加到 qBittorrent"
        )
        table.add_row(
            "添加失败", 
            f"[red]{stats.get('failed_adds', 0)}[/]",
            "添加到 qBittorrent 失败"
        )
        table.add_row(
            "重复跳过", 
            f"[yellow]{stats.get('duplicates_skipped', 0)}[/]",
            "已存在或防抖跳过"
        )
        table.add_row(
            "无效链接", 
            f"[red]{stats.get('invalid_magnets', 0)}[/]",
            "格式错误的磁力链接"
        )
        
        # 性能指标
        table.add_row(
            "检查次数", 
            str(stats.get("checks_performed", 0)),
            "剪贴板检查总次数"
        )
        table.add_row(
            "检查频率", 
            f"{stats.get('checks_per_minute', 0):.2f}/min",
            "每分钟检查次数"
        )
        table.add_row(
            "平均耗时", 
            f"{stats.get('avg_check_time_ms', 0):.3f} ms",
            "单次检查平均耗时"
        )
        
        console.print(table)
    
    @classmethod
    def show_category_stats(cls, categories: List[Dict[str, Any]]) -> None:
        """显示分类统计
        
        Args:
            categories: 分类统计列表
        """
        if not categories:
            return
        
        if not RICH_AVAILABLE:
            print("\n--- 分类统计 ---")
            for cat in categories:
                print(f"  {cat.get('category', 'unknown')}: {cat.get('count', 0)}")
            return
        
        table = Table(
            title="[bold cyan]分类统计[/]",
            box=box.SIMPLE,
            show_header=True
        )
        table.add_column("分类", style="cyan")
        table.add_column("数量", justify="right", style="green")
        table.add_column("占比", justify="right")
        
        total = sum(c.get("count", 0) for c in categories)
        for cat in categories:
            count = cat.get("count", 0)
            pct = (count / total * 100) if total > 0 else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            table.add_row(
                cat.get("category", "unknown"),
                str(count),
                f"{bar} {pct:.1f}%"
            )
        
        console.print(table)


class ProgressDisplay:
    """进度指示组件
    
    使用示例:
        >>> with ProgressDisplay("处理中...") as progress:
        ...     for i in range(100):
        ...         progress.update(advance=1)
    """
    
    def __init__(self, description: str = "处理中..."):
        self.description = description
        self._progress: Optional[Progress] = None
        self._task = None
    
    def __enter__(self):
        if not RICH_AVAILABLE:
            print(f"{self.description}...")
            return self
        
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=40),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True
        )
        self._progress.start()
        self._task = self._progress.add_task(self.description, total=None)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._progress:
            self._progress.stop()
    
    def update(self, advance: float = 1, description: Optional[str] = None) -> None:
        """更新进度
        
        Args:
            advance: 进度增量
            description: 更新描述（可选）
        """
        if self._progress and self._task is not None:
            self._progress.update(
                self._task,
                advance=advance,
                description=description or self.description
            )
    
    def set_total(self, total: float) -> None:
        """设置总数
        
        Args:
            total: 总任务数
        """
        if self._progress and self._task is not None:
            self._progress.update(self._task, total=total)


class SpinnerStatus:
    """Spinner 状态指示器
    
    使用示例:
        >>> with SpinnerStatus("正在加载...") as spinner:
        ...     # 执行耗时操作
        ...     spinner.update("正在处理...")
    """
    
    def __init__(self, message: str = "处理中...", spinner: str = "dots"):
        self.message = message
        self.spinner = spinner
        self._live: Optional[Live] = None
    
    def __enter__(self):
        if not RICH_AVAILABLE:
            print(f"{self.message}...")
            return self
        
        self._live = Live(
            Spinner(self.spinner, text=self.message),
            console=console,
            transient=True,
            refresh_per_second=10
        )
        self._live.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._live:
            self._live.stop()
    
    def update(self, message: str) -> None:
        """更新消息
        
        Args:
            message: 新消息
        """
        self.message = message
        if self._live:
            self._live.update(Spinner(self.spinner, text=f"[cyan]{message}[/]"))


class OutputFormatter:
    """多格式输出支持"""
    
    @staticmethod
    def output(data: Dict[str, Any], format_type: str = "table") -> None:
        """根据格式类型输出数据
        
        Args:
            data: 要输出的数据
            format_type: 输出格式 - table/json/yaml
        """
        if format_type == "json":
            OutputFormatter._output_json(data)
        elif format_type == "yaml":
            OutputFormatter._output_yaml(data)
        else:
            OutputFormatter._output_table(data)
    
    @staticmethod
    def _output_json(data: Dict[str, Any]) -> None:
        """JSON 格式输出"""
        json_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        if RICH_AVAILABLE:
            syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
            console.print(syntax)
        else:
            print(json_str)
    
    @staticmethod
    def _output_yaml(data: Dict[str, Any]) -> None:
        """YAML 格式输出"""
        try:
            import yaml
            yaml_str = yaml.dump(data, allow_unicode=True, sort_keys=False)
            if RICH_AVAILABLE:
                syntax = Syntax(yaml_str, "yaml", theme="monokai", line_numbers=True)
                console.print(syntax)
            else:
                print(yaml_str)
        except ImportError:
            console.print("[yellow]提示: 安装 PyYAML 以获得更好的 YAML 支持[/]")
            OutputFormatter._output_json(data)
    
    @staticmethod
    def _output_table(data: Dict[str, Any], title: str = "") -> None:
        """表格格式输出"""
        if not RICH_AVAILABLE:
            for key, value in data.items():
                print(f"  {key}: {value}")
            return
        
        table = Table(
            title=f"[bold cyan]{title}[/]" if title else None,
            box=box.SIMPLE_HEAD
        )
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        
        for key, value in data.items():
            if isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False)
            table.add_row(str(key), str(value))
        
        console.print(table)


# 便捷函数
def print_banner(
    title: str, 
    version: str, 
    description: str = "",
    subtitle: str = ""
) -> None:
    """打印应用横幅"""
    StyledOutput.banner(title, version, description, subtitle)

def print_success(message: str) -> None:
    """打印成功消息"""
    StyledOutput.success(message)

def print_error(message: str) -> None:
    """打印错误消息"""
    StyledOutput.error(message)

def print_warning(message: str) -> None:
    """打印警告消息"""
    StyledOutput.warning(message)

def print_info(message: str) -> None:
    """打印信息消息"""
    StyledOutput.info(message)


def print_startup_info(config_info: Dict[str, Any]) -> None:
    """打印启动信息面板
    
    Args:
        config_info: 配置信息字典
    """
    if not RICH_AVAILABLE:
        print("\n--- 启动信息 ---")
        for key, value in config_info.items():
            print(f"  {key}: {value}")
        print(f"{'='*50}")
        return
    
    from rich.text import Text
    
    content = Text()
    content.append("📡 qBittorrent: ", style="cyan")
    content.append(f"{config_info.get('host', 'N/A')}\n", style="white")
    
    if config_info.get('ai_enabled'):
        content.append("🧠 AI 分类: ", style="cyan")
        content.append("已启用\n", style="green")
    else:
        content.append("🧠 AI 分类: ", style="cyan")
        content.append("已禁用\n", style="dim")
    
    if config_info.get('database_enabled'):
        content.append("💾 数据库: ", style="cyan")
        content.append(f"{config_info.get('database_path', '默认路径')}\n", style="white")
    
    content.append("⏱️  检查间隔: ", style="cyan")
    content.append(f"{config_info.get('check_interval', '1.0')} 秒\n", style="white")
    
    content.append("📊 指标: ", style="cyan")
    if config_info.get('metrics_enabled'):
        content.append(
            f"http://{config_info.get('metrics_host', 'localhost')}:"
            f"{config_info.get('metrics_port', 9090)}\n",
            style="green"
        )
    else:
        content.append("已禁用\n", style="dim")
    
    console.print(Panel(
        content,
        title="[bold green]剪贴板监控已启动[/]",
        box=box.ROUNDED,
        border_style="green",
        padding=(1, 2)
    ))
    
    console.print("[dim]按 Ctrl+C 停止监控 | 使用 --log-level DEBUG 查看详细日志[/]\n")
