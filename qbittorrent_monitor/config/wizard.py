"""交互式配置向导模块

提供命令行交互式配置生成工具，帮助用户快速创建配置文件。

使用示例:
    >>> from qbittorrent_monitor.config.wizard import run_wizard
    >>> config = run_wizard()
    
或者命令行:
    $ python run.py --init
"""

from __future__ import annotations

import getpass
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# 尝试导入 Rich

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich import box
    from rich.text import Text
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

logger = logging.getLogger(__name__)


class ConfigWizard:
    """交互式配置向导
    
    通过交互式问答帮助用户生成配置文件。
    """
    
    def __init__(self):
        self.config_data: dict = {}
        
    def _print(self, text: str, style: str = "") -> None:
        """打印带样式的文本"""
        if RICH_AVAILABLE and console:
            if style == "header":
                console.print(Panel(text, style="bold magenta", box=box.DOUBLE))
            elif style == "success":
                console.print(f"[green]✓[/] {text}")
            elif style == "warning":
                console.print(f"[yellow]⚠[/] {text}")
            elif style == "error":
                console.print(f"[red]✗[/] {text}")
            elif style == "info":
                console.print(f"[cyan]ℹ[/] {text}")
            else:
                console.print(text)
        else:
            # Fallback
            emoji_map = {
                "success": "✓",
                "warning": "⚠",
                "error": "✗",
                "info": "ℹ",
            }
            emoji = emoji_map.get(style, "")
            prefix = f"{emoji} " if emoji else ""
            print(f"{prefix}{text}")
    
    def _input(self, prompt: str, default: Optional[str] = None) -> str:
        """带默认值的输入"""
        if default:
            full_prompt = f"{prompt} [{default}]: "
        else:
            full_prompt = f"{prompt}: "
        
        value = input(full_prompt).strip()
        return value if value else (default or "")
    
    def _confirm(self, prompt: str, default: bool = False) -> bool:
        """确认提示"""
        suffix = " [Y/n]: " if default else " [y/N]: "
        response = input(f"{prompt}{suffix}").strip().lower()
        
        if not response:
            return default
        return response in ("y", "yes", "true", "1")
    
    def _print_header(self, title: str) -> None:
        """打印章节标题"""
        if RICH_AVAILABLE and console:
            console.print(f"\n[bold blue]📦 {title}[/]")
            console.print("─" * 50, style="dim")
        else:
            print(f"\n📦 {title}")
            print("─" * 40)
    
    def run(self) -> dict:
        """运行配置向导
        
        Returns:
            生成的配置字典
        """
        # 欢迎信息
        self._print(
            "qBittorrent Clipboard Monitor - 配置向导\n\n"
            "本向导将帮助您生成配置文件。只需回答几个问题，\n"
            "即可快速完成配置。",
            "header"
        )
        
        # qBittorrent 配置
        self._configure_qbittorrent()
        
        # AI 配置
        self._configure_ai()
        
        # 基本设置
        self._configure_basic()
        
        # 分类配置
        self._configure_categories()
        
        # 保存配置
        return self._save_config()
    
    def _configure_qbittorrent(self) -> None:
        """配置 qBittorrent 连接"""
        self._print_header("qBittorrent 连接配置")
        
        self._print("请输入 qBittorrent Web UI 的连接信息：", "info")
        self._print("提示：在 qBittorrent 中启用 Web UI：工具 → 选项 → Web UI", "info")
        
        host = self._input("服务器地址", "localhost")
        port = self._input("Web UI 端口", "8080")
        username = self._input("用户名", "admin")
        password = getpass.getpass("密码: ")
        
        while not password:
            self._print("密码不能为空！", "error")
            password = getpass.getpass("密码: ")
        
        use_https = self._confirm("使用 HTTPS?", False)
        
        self.config_data["qbittorrent"] = {
            "host": host,
            "port": int(port),
            "username": username,
            "password": password,
            "use_https": use_https,
        }
        
        self._print("qBittorrent 配置完成", "success")
    
    def _configure_ai(self) -> None:
        """配置 AI 分类"""
        self._print_header("AI 自动分类配置（可选）")
        
        self._print("AI 分类可以自动识别内容类型（电影/电视剧/动漫等）", "info")
        
        enabled = self._confirm("启用 AI 自动分类?", False)
        
        if enabled:
            self._print("\n支持的 AI 服务商:", "info")
            self._print("  1. DeepSeek (推荐，国内可用)")
            self._print("  2. MiniMax")
            self._print("  3. OpenAI")
            self._print("  4. 其他 (自定义)")
            
            choice = self._input("请选择", "1")
            
            providers = {
                "1": ("deepseek-chat", "https://api.deepseek.com/v1"),
                "2": ("MiniMax-M2.5", "https://api.minimaxi.com/v1"),
                "3": ("gpt-3.5-turbo", "https://api.openai.com/v1"),
            }
            
            if choice in providers:
                model, base_url = providers[choice]
            else:
                model = self._input("模型名称")
                base_url = self._input("API 基础 URL")
            
            api_key = getpass.getpass("API 密钥: ")
            
            while not api_key:
                self._print("API 密钥不能为空！", "error")
                api_key = getpass.getpass("API 密钥: ")
            
            self.config_data["ai"] = {
                "enabled": True,
                "api_key": api_key,
                "model": model,
                "base_url": base_url,
                "timeout": 30,
                "max_retries": 3,
            }
            self._print("AI 配置完成", "success")
        else:
            self.config_data["ai"] = {"enabled": False}
            self._print("AI 分类已禁用（可在之后启用）", "info")
    
    def _configure_basic(self) -> None:
        """配置基本设置"""
        self._print_header("基本设置")
        
        interval = self._input("剪贴板检查间隔（秒，建议 0.5-2.0）", "1.0")
        log_level = self._input("日志级别 (DEBUG/INFO/WARNING/ERROR)", "INFO")
        
        # 验证日志级别
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        log_level = log_level.upper()
        if log_level not in valid_levels:
            self._print(f"无效的日志级别，使用默认 INFO", "warning")
            log_level = "INFO"
        
        self.config_data["check_interval"] = float(interval)
        self.config_data["log_level"] = log_level
        
        # 数据持久化
        enable_db = self._confirm("启用数据持久化（记录历史）?", True)
        if enable_db:
            self.config_data["database"] = {
                "enabled": True,
                "db_path": "~/.local/share/qb-monitor/monitor.db",
                "auto_cleanup_days": 30,
            }
        
        # 指标
        enable_metrics = self._confirm("启用 Prometheus 指标导出?", False)
        if enable_metrics:
            self.config_data["metrics"] = {
                "enabled": True,
                "host": "0.0.0.0",
                "port": 9090,
                "path": "/metrics",
            }
        
        self._print("基本设置完成", "success")
    
    def _configure_categories(self) -> None:
        """配置分类规则"""
        self._print_header("分类规则配置（可选）")
        
        self._print("可以设置关键词规则，自动将内容分类到不同目录", "info")
        
        if not self._confirm("是否配置分类规则?", True):
            return
        
        categories = {}
        
        # 电影
        if self._confirm("添加 [电影] 分类?", True):
            path = self._input("保存路径", "/downloads/movies")
            categories["movies"] = {
                "save_path": path,
                "keywords": ["Movie", "电影", "1080p", "2160p", "4K", "BluRay"],
            }
        
        # 电视剧
        if self._confirm("添加 [电视剧] 分类?", True):
            path = self._input("保存路径", "/downloads/tv")
            categories["tv"] = {
                "save_path": path,
                "keywords": ["S01", "S02", "E01", "Season", "Series", "TV"],
            }
        
        # 动漫
        if self._confirm("添加 [动漫] 分类?", False):
            path = self._input("保存路径", "/downloads/anime")
            categories["anime"] = {
                "save_path": path,
                "keywords": ["Anime", "动画", "动漫", "EP", "第"],
            }
        
        # 音乐
        if self._confirm("添加 [音乐] 分类?", False):
            path = self._input("保存路径", "/downloads/music")
            categories["music"] = {
                "save_path": path,
                "keywords": ["Music", "FLAC", "MP3", "Album"],
            }
        
        # 其他
        if self._confirm("添加 [软件/游戏] 分类?", False):
            path = self._input("保存路径", "/downloads/software")
            categories["software"] = {
                "save_path": path,
                "keywords": ["Software", "Game", "APP", "破解"],
            }
        
        if categories:
            self.config_data["categories"] = categories
            self._print(f"已配置 {len(categories)} 个分类", "success")
    
    def _save_config(self) -> dict:
        """保存配置到文件
        
        Returns:
            配置字典
        """
        self._print_header("保存配置")
        
        # 默认路径
        default_path = Path.home() / ".config" / "qb-monitor" / "config.json"
        
        self._print(f"默认配置文件路径: {default_path}", "info")
        
        custom_path = self._input("配置文件路径（留空使用默认）", str(default_path))
        path = Path(custom_path)
        
        # 确认覆盖
        if path.exists():
            if not self._confirm(f"文件已存在，是否覆盖?", False):
                self._print("已取消保存", "warning")
                return self.config_data
        
        try:
            # 创建目录
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存配置
            import json
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
            
            # 设置权限（仅当前用户可读写）
            os.chmod(path, 0o600)
            
            self._print(f"配置已保存到: {path}", "success")
            
            # 安全提示
            self._print("\n🔒 安全提示:", "info")
            self._print("  • 配置文件已设置为仅当前用户可读写")
            self._print("  • 请勿将配置文件提交到 Git 仓库")
            self._print("  • 建议定期备份配置文件")
            
            # 下一步提示
            self._print("\n🚀 下一步:", "success")
            self._print(f"  运行: python run.py --config {path}")
            
        except Exception as e:
            self._print(f"保存失败: {e}", "error")
            raise
        
        return self.config_data


def run_wizard() -> dict:
    """运行配置向导的便捷函数
    
    Returns:
        生成的配置字典
        
    Example:
        >>> config = run_wizard()
        >>> print(config)
    """
    wizard = ConfigWizard()
    return wizard.run()


# 命令行入口
if __name__ == "__main__":
    # 直接运行此模块时启动向导
    try:
        run_wizard()
    except KeyboardInterrupt:
        print("\n\n已取消配置向导")
        sys.exit(0)
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)
