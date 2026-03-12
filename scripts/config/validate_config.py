#!/usr/bin/env python3
"""
配置验证工具

功能:
- 验证配置文件格式和结构
- 检查配置项有效性
- 生成配置模板
- 提供修复建议

用法:
    python scripts/config/validate_config.py --config config.json
    python scripts/config/validate_config.py --template development
    python scripts/config/validate_config.py --env-file .env
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from qbittorrent_monitor.config import AppConfig, ConfigManager
    from pydantic import ValidationError
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False


@dataclass
class ValidationError:
    """验证错误"""
    path: str
    message: str
    severity: str = "error"  # error, warning, info
    suggestion: str = ""


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    infos: List[ValidationError] = field(default_factory=list)

    def add_error(self, path: str, message: str, suggestion: str = ""):
        self.errors.append(ValidationError(path, message, "error", suggestion))
        self.is_valid = False

    def add_warning(self, path: str, message: str, suggestion: str = ""):
        self.warnings.append(ValidationError(path, message, "warning", suggestion))

    def add_info(self, path: str, message: str):
        self.infos.append(ValidationError(path, message, "info"))

    def print_report(self):
        """打印验证报告"""
        print("\n" + "=" * 60)
        print("配置验证报告")
        print("=" * 60)

        if self.is_valid and not self.warnings:
            print("✅ 配置验证通过！")
        elif self.is_valid:
            print("⚠️  配置有效，但有警告需要关注")
        else:
            print("❌ 配置验证失败")

        if self.errors:
            print(f"\n🔴 错误 ({len(self.errors)}):")
            for err in self.errors:
                print(f"  [{err.path}] {err.message}")
                if err.suggestion:
                    print(f"   💡 建议: {err.suggestion}")

        if self.warnings:
            print(f"\n🟡 警告 ({len(self.warnings)}):")
            for warn in self.warnings:
                print(f"  [{warn.path}] {warn.message}")
                if warn.suggestion:
                    print(f"   💡 建议: {warn.suggestion}")

        if self.infos:
            print(f"\n🔵 信息 ({len(self.infos)}):")
            for info in self.infos:
                print(f"  [{info.path}] {info.message}")

        print("\n" + "=" * 60)


class ConfigValidator:
    """配置验证器"""

    # 必需配置节
    REQUIRED_SECTIONS = ['qbittorrent', 'deepseek', 'categories']

    # 有效的日志级别
    VALID_LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    # 有效的通知服务
    VALID_NOTIFICATION_SERVICES = ['telegram', 'discord', 'email', 'webhook', 'apprise']

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or PROJECT_ROOT / 'qbittorrent_monitor' / 'config.json'
        self.result = ValidationResult()

    def validate(self) -> ValidationResult:
        """执行完整验证"""
        print(f"🔍 正在验证配置文件: {self.config_path}")

        # 1. 检查文件存在
        if not self.config_path.exists():
            self.result.add_error(
                "file",
                f"配置文件不存在: {self.config_path}",
                "运行 'python run.py' 生成默认配置，或使用 --template 生成模板"
            )
            return self.result

        # 2. 检查文件权限
        self._check_file_permissions()

        # 3. 解析配置文件
        config_data = self._load_config()
        if config_data is None:
            return self.result

        # 4. 基础结构验证
        self._validate_structure(config_data)

        # 5. qBittorrent配置验证
        self._validate_qbittorrent(config_data.get('qbittorrent', {}))

        # 6. DeepSeek配置验证
        self._validate_deepseek(config_data.get('deepseek', {}))

        # 7. 分类配置验证
        self._validate_categories(config_data.get('categories', {}))

        # 8. 爬虫配置验证
        self._validate_web_crawler(config_data.get('web_crawler', {}))

        # 9. 通知配置验证
        self._validate_notifications(config_data.get('notifications', {}))

        # 10. 全局配置验证
        self._validate_global_config(config_data)

        # 11. 使用Pydantic进行完整验证
        if HAS_PYDANTIC:
            self._validate_with_pydantic(config_data)

        # 12. 安全检查
        self._security_checks(config_data)

        # 13. 性能建议
        self._performance_suggestions(config_data)

        return self.result

    def _check_file_permissions(self):
        """检查文件权限"""
        try:
            stat = self.config_path.stat()
            mode = stat.st_mode

            # 检查是否全局可读（可能包含敏感信息）
            if mode & 0o044:
                self.result.add_warning(
                    "file.permissions",
                    "配置文件对其他人可读，可能泄露敏感信息",
                    f"运行: chmod 600 {self.config_path}"
                )
        except Exception as e:
            self.result.add_warning("file.permissions", f"无法检查文件权限: {e}")

    def _load_config(self) -> Optional[Dict[str, Any]]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.suffix in ['.yaml', '.yml']:
                    import yaml
                    return yaml.safe_load(f)
                elif self.config_path.suffix == '.toml':
                    import tomllib
                    return tomllib.load(f)
                else:
                    return json.load(f)
        except json.JSONDecodeError as e:
            self.result.add_error(
                "file.parse",
                f"JSON解析错误: {e}",
                "检查JSON语法，确保引号、括号匹配"
            )
        except Exception as e:
            self.result.add_error("file.load", f"无法加载配置文件: {e}")
        return None

    def _validate_structure(self, config: Dict[str, Any]):
        """验证基础结构"""
        for section in self.REQUIRED_SECTIONS:
            if section not in config:
                self.result.add_error(
                    f"structure.{section}",
                    f"缺少必需的配置节: {section}",
                    f"在配置文件中添加 '{section}' 配置节"
                )

    def _validate_qbittorrent(self, qbt_config: Dict[str, Any]):
        """验证qBittorrent配置"""
        if not qbt_config:
            return

        # 检查必需字段
        required_fields = ['host', 'port', 'username', 'password']
        for field in required_fields:
            if field not in qbt_config:
                self.result.add_error(
                    f"qbittorrent.{field}",
                    f"缺少必需字段: {field}",
                    f"在 qbittorrent 配置中添加 '{field}'"
                )

        # 验证主机地址
        host = qbt_config.get('host', '')
        if host:
            if host in ['localhost', '127.0.0.1']:
                self.result.add_info(
                    "qbittorrent.host",
                    "使用本地qBittorrent连接"
                )
            elif host.startswith('192.168.') or host.startswith('10.'):
                self.result.add_info(
                    "qbittorrent.host",
                    "使用内网qBittorrent连接"
                )

        # 验证端口
        port = qbt_config.get('port', 0)
        if port:
            if not (1 <= port <= 65535):
                self.result.add_error(
                    "qbittorrent.port",
                    f"端口号无效: {port}",
                    "端口号必须在 1-65535 之间"
                )
            elif port < 1024:
                self.result.add_warning(
                    "qbittorrent.port",
                    f"使用特权端口: {port}",
                    "建议使用1024以上的端口，避免权限问题"
                )

        # 安全警告
        password = qbt_config.get('password', '')
        if password:
            if password in ['password', 'admin', '123456', '']:
                self.result.add_warning(
                    "qbittorrent.password",
                    "使用弱密码或默认密码",
                    "修改qBittorrent密码为强密码"
                )
            elif len(password) < 8:
                self.result.add_warning(
                    "qbittorrent.password",
                    "密码长度过短（少于8位）",
                    "使用至少8位的强密码"
                )

        # HTTPS检查
        use_https = qbt_config.get('use_https', False)
        verify_ssl = qbt_config.get('verify_ssl', True)
        if not use_https and not host.startswith('192.168.'):
            self.result.add_warning(
                "qbittorrent.use_https",
                "未启用HTTPS连接",
                "公网访问建议启用HTTPS: \"use_https\": true"
            )
        if use_https and not verify_ssl:
            self.result.add_warning(
                "qbittorrent.verify_ssl",
                "HTTPS启用但SSL验证已禁用",
                "生产环境建议启用SSL验证: \"verify_ssl\": true"
            )

    def _validate_deepseek(self, deepseek_config: Dict[str, Any]):
        """验证DeepSeek配置"""
        if not deepseek_config:
            return

        api_key = deepseek_config.get('api_key', '')
        if not api_key:
            self.result.add_warning(
                "deepseek.api_key",
                "未配置DeepSeek API密钥",
                "设置环境变量 DEEPSEEK_API_KEY 或在配置中添加 api_key"
            )
        elif api_key.startswith('${') and api_key.endswith('}'):
            env_var = api_key[2:-1]
            if not os.getenv(env_var):
                self.result.add_warning(
                    "deepseek.api_key",
                    f"API密钥引用环境变量但未设置: {env_var}",
                    f"运行: export {env_var}=your_api_key"
                )
        elif len(api_key) < 20:
            self.result.add_warning(
                "deepseek.api_key",
                "API密钥格式异常",
                "检查API密钥是否正确"
            )

        # 验证base_url
        base_url = deepseek_config.get('base_url', '')
        if base_url:
            if not base_url.startswith(('http://', 'https://')):
                self.result.add_error(
                    "deepseek.base_url",
                    f"无效的base_url: {base_url}",
                    "URL必须以 http:// 或 https:// 开头"
                )
            elif base_url.startswith('http://') and 'localhost' not in base_url:
                self.result.add_warning(
                    "deepseek.base_url",
                    "使用不安全的HTTP协议",
                    "建议使用HTTPS: \"base_url\": \"https://...\""
                )

        # 验证超时和重试
        timeout = deepseek_config.get('timeout', 30)
        if timeout > 120:
            self.result.add_warning(
                "deepseek.timeout",
                f"API超时时间过长: {timeout}秒",
                "建议设置为30-60秒"
            )

        max_retries = deepseek_config.get('max_retries', 3)
        if max_retries > 5:
            self.result.add_warning(
                "deepseek.max_retries",
                f"重试次数过多: {max_retries}",
                "建议设置为1-3次，避免长时间等待"
            )

    def _validate_categories(self, categories: Dict[str, Any]):
        """验证分类配置"""
        if not categories:
            return

        if len(categories) == 0:
            self.result.add_error(
                "categories",
                "至少需要配置一个分类",
                "添加至少一个分类配置"
            )
            return

        # 检查保存路径重复
        save_paths: Dict[str, str] = {}
        for name, config in categories.items():
            save_path = config.get('savePath') or config.get('save_path', '')
            if save_path:
                if save_path in save_paths:
                    self.result.add_error(
                        f"categories.{name}.savePath",
                        f"保存路径与其他分类重复: {save_path}",
                        f"与分类 '{save_paths[save_path]}' 路径冲突，请修改"
                    )
                save_paths[save_path] = name

            # 检查必需字段
            if not save_path:
                self.result.add_error(
                    f"categories.{name}.savePath",
                    f"分类 '{name}' 缺少 savePath",
                    f"为分类 '{name}' 添加 savePath"
                )

            # 验证路径格式
            if save_path and not save_path.endswith('/'):
                self.result.add_warning(
                    f"categories.{name}.savePath",
                    f"保存路径建议以/结尾: {save_path}",
                    f"修改为: \"{save_path}/\""
                )

        # 检查是否有other分类
        if 'other' not in categories:
            self.result.add_warning(
                "categories",
                "缺少 'other' 分类（其他内容）",
                "建议添加 'other' 分类作为默认分类"
            )

        # 检查优先级
        priorities = []
        for name, config in categories.items():
            priority = config.get('priority', 0)
            if priority in priorities:
                self.result.add_info(
                    f"categories.{name}.priority",
                    f"分类 '{name}' 的优先级与其他分类相同: {priority}"
                )
            priorities.append(priority)

    def _validate_web_crawler(self, crawler_config: Dict[str, Any]):
        """验证爬虫配置"""
        if not crawler_config:
            return

        enabled = crawler_config.get('enabled', True)
        if not enabled:
            self.result.add_info(
                "web_crawler.enabled",
                "网页爬虫已禁用"
            )
            return

        # 验证并发数
        max_concurrent = crawler_config.get('max_concurrent_extractions', 3)
        if max_concurrent > 10:
            self.result.add_warning(
                "web_crawler.max_concurrent_extractions",
                f"并发数过高: {max_concurrent}",
                "建议设置为1-5，避免资源占用过多"
            )
        elif max_concurrent == 1:
            self.result.add_info(
                "web_crawler.max_concurrent_extractions",
                "使用单线程模式（适合低配置服务器）"
            )

        # 验证超时
        page_timeout = crawler_config.get('page_timeout', 60000)
        if page_timeout < 10000:
            self.result.add_warning(
                "web_crawler.page_timeout",
                f"页面超时时间过短: {page_timeout}ms",
                "建议至少设置为30000ms"
            )

        # 验证代理
        proxy = crawler_config.get('proxy')
        if proxy:
            if not proxy.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
                self.result.add_error(
                    "web_crawler.proxy",
                    f"代理地址格式错误: {proxy}",
                    "代理地址必须以 http://、https://、socks4:// 或 socks5:// 开头"
                )

    def _validate_notifications(self, notif_config: Dict[str, Any]):
        """验证通知配置"""
        if not notif_config:
            return

        enabled = notif_config.get('enabled', False)
        if not enabled:
            self.result.add_info(
                "notifications.enabled",
                "通知功能已禁用"
            )
            return

        services = notif_config.get('services', [])
        for service in services:
            if service not in self.VALID_NOTIFICATION_SERVICES:
                self.result.add_error(
                    "notifications.services",
                    f"未知的通知服务: {service}",
                    f"有效值: {', '.join(self.VALID_NOTIFICATION_SERVICES)}"
                )

        # 检查Telegram配置
        if 'telegram' in services:
            api_token = notif_config.get('api_token')
            chat_id = notif_config.get('chat_id')
            if not api_token:
                self.result.add_error(
                    "notifications.api_token",
                    "启用了Telegram通知但未配置api_token",
                    "设置 api_token 或从环境变量读取"
                )
            if not chat_id:
                self.result.add_error(
                    "notifications.chat_id",
                    "启用了Telegram通知但未配置chat_id",
                    "设置 chat_id 或从环境变量读取"
                )

        # 检查邮件配置
        if 'email' in services:
            email_config = notif_config.get('email_config', {})
            required_email_fields = ['smtp_host', 'username', 'password']
            for field in required_email_fields:
                if not email_config.get(field):
                    self.result.add_error(
                        f"notifications.email_config.{field}",
                        f"启用了邮件通知但缺少: {field}",
                        f"在 email_config 中添加 '{field}'"
                    )

    def _validate_global_config(self, config: Dict[str, Any]):
        """验证全局配置"""
        # 日志级别
        log_level = config.get('log_level', 'INFO')
        if log_level not in self.VALID_LOG_LEVELS:
            self.result.add_error(
                "log_level",
                f"无效的日志级别: {log_level}",
                f"有效值: {', '.join(self.VALID_LOG_LEVELS)}"
            )

        # 检查间隔
        check_interval = config.get('check_interval', 2.0)
        if check_interval < 0.1:
            self.result.add_warning(
                "check_interval",
                f"检查间隔过短: {check_interval}秒",
                "过短的间隔会增加CPU占用，建议 >= 0.5秒"
            )
        elif check_interval > 10:
            self.result.add_warning(
                "check_interval",
                f"检查间隔过长: {check_interval}秒",
                "过长的间隔会降低响应速度，建议 <= 5秒"
            )

        # 热加载
        hot_reload = config.get('hot_reload', True)
        if hot_reload:
            self.result.add_info(
                "hot_reload",
                "配置热加载已启用（配置文件修改后自动生效）"
            )

    def _validate_with_pydantic(self, config: Dict[str, Any]):
        """使用Pydantic进行完整验证"""
        try:
            AppConfig(**config)
        except ValidationError as e:
            for error in e.errors():
                path = '.'.join(str(x) for x in error['loc'])
                self.result.add_error(
                    path,
                    error['msg'],
                    "检查配置项类型和格式"
                )
        except Exception as e:
            self.result.add_error(
                "pydantic",
                f"Pydantic验证失败: {e}",
                "检查配置文件结构"
            )

    def _security_checks(self, config: Dict[str, Any]):
        """安全检查"""
        # 检查是否使用了明文密码
        qbt_config = config.get('qbittorrent', {})
        if qbt_config.get('password') and not qbt_config.get('hashed_password'):
            self.result.add_warning(
                "security.password",
                "使用明文密码存储",
                "建议使用 hashed_password 存储哈希后的密码（需要passlib库）"
            )

        # 检查是否启用了SSL验证
        if qbt_config.get('use_https') and not qbt_config.get('verify_ssl', True):
            self.result.add_warning(
                "security.ssl",
                "HTTPS启用但禁用了SSL证书验证",
                "生产环境建议启用 verify_ssl: true"
            )

        # 检查API密钥
        deepseek_config = config.get('deepseek', {})
        api_key = deepseek_config.get('api_key', '')
        if api_key and not api_key.startswith('${'):
            self.result.add_info(
                "security.api_key",
                "API密钥直接存储在配置文件中",
                "建议使用环境变量: \"api_key\": \"${DEEPSEEK_API_KEY}\""
            )

    def _performance_suggestions(self, config: Dict[str, Any]):
        """性能建议"""
        # 检查缓存配置
        check_interval = config.get('check_interval', 2.0)
        if check_interval < 0.5:
            self.result.add_info(
                "performance.check_interval",
                "高频率监控模式（CPU占用可能较高）"
            )

        # 检查爬虫配置
        crawler_config = config.get('web_crawler', {})
        if crawler_config.get('enabled', True):
            max_concurrent = crawler_config.get('max_concurrent_extractions', 3)
            if max_concurrent > 5:
                self.result.add_info(
                    "performance.crawler",
                    "爬虫并发数较高（适合高性能服务器）"
                )
            elif max_concurrent == 1:
                self.result.add_info(
                    "performance.crawler",
                    "爬虫单线程模式（适合低配置服务器）"
                )


def generate_template(template_type: str = 'development') -> str:
    """生成配置模板"""
    from qbittorrent_monitor.config import ConfigTemplate

    templates = {
        'development': ConfigTemplate.get_development_template,
        'production': ConfigTemplate.get_production_template,
        'testing': ConfigTemplate.get_testing_template,
    }

    if template_type not in templates:
        available = ', '.join(templates.keys())
        raise ValueError(f"未知模板类型: {template_type}. 可用: {available}")

    template = templates[template_type]()

    # 添加注释头
    header = {
        'development': '''{
    "_comment": "开发环境配置 - 详细日志、热加载、调试功能开启",
    "_warning": "请勿在生产环境使用此配置"''',
        'production': '''{
    "_comment": "生产环境配置 - 性能优化、安全检查",
    "_warning": "请确保已设置所有环境变量，如 QBT_PASSWORD, DEEPSEEK_API_KEY"''',
        'testing': '''{
    "_comment": "测试环境配置 - 快速执行、禁用外部服务",
    "_warning": "仅用于自动化测试"''',
    }

    # 手动构建带注释的JSON
    lines = [header.get(template_type, '{')]

    def format_value(v, indent=4):
        if isinstance(v, dict):
            if not v:
                return "{}"
            items = []
            for key, val in v.items():
                items.append(f'{" " * indent}"{key}": {format_value(val, indent + 4)}')
            return "{\n" + ",\n".join(items) + f'\n{" " * (indent - 4)}}}'
        elif isinstance(v, list):
            if not v:
                return "[]"
            if all(isinstance(x, str) for x in v):
                return json.dumps(v, ensure_ascii=False)
            items = []
            for item in v:
                items.append(f'{" " * indent}{format_value(item, indent + 4)}')
            return "[\n" + ",\n".join(items) + f'\n{" " * (indent - 4)}}]'
        elif isinstance(v, str):
            return json.dumps(v, ensure_ascii=False)
        elif isinstance(v, bool):
            return "true" if v else "false"
        elif isinstance(v, (int, float)):
            return str(v)
        else:
            return json.dumps(v, ensure_ascii=False)

    for key, value in template.items():
        lines.append(f'    "{key}": {format_value(value)},')

    # 移除最后一个逗号
    if lines[-1].endswith(','):
        lines[-1] = lines[-1][:-1]

    lines.append('}')

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='配置验证工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 验证默认配置文件
  python validate_config.py

  # 验证指定配置文件
  python validate_config.py --config /path/to/config.json

  # 生成配置模板
  python validate_config.py --template development
  python validate_config.py --template production
  python validate_config.py --template testing

  # 验证并应用环境变量
  python validate_config.py --env-file .env.production
        '''
    )

    parser.add_argument(
        '--config', '-c',
        type=Path,
        help='配置文件路径'
    )

    parser.add_argument(
        '--template', '-t',
        choices=['development', 'production', 'testing'],
        help='生成配置模板'
    )

    parser.add_argument(
        '--env-file',
        type=Path,
        help='环境变量文件路径'
    )

    parser.add_argument(
        '--output', '-o',
        type=Path,
        help='输出文件路径（用于模板生成）'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='静默模式，只返回退出码'
    )

    args = parser.parse_args()

    # 加载环境变量文件
    if args.env_file:
        if args.env_file.exists():
            with open(args.env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
            if not args.quiet:
                print(f"✅ 已加载环境变量: {args.env_file}")
        else:
            print(f"❌ 环境变量文件不存在: {args.env_file}")
            sys.exit(1)

    # 生成模板
    if args.template:
        try:
            template_content = generate_template(args.template)

            if args.output:
                with open(args.output, 'w') as f:
                    f.write(template_content)
                if not args.quiet:
                    print(f"✅ 配置模板已生成: {args.output}")
            else:
                print(template_content)
            sys.exit(0)
        except Exception as e:
            print(f"❌ 生成模板失败: {e}")
            sys.exit(1)

    # 验证配置
    validator = ConfigValidator(args.config)
    result = validator.validate()

    if not args.quiet:
        result.print_report()

    sys.exit(0 if result.is_valid else 1)


if __name__ == '__main__':
    main()
