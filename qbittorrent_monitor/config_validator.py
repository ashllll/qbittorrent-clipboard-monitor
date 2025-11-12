"""
配置验证器
验证环境变量和配置文件的完整性和正确性
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """验证级别"""
    ERROR = "ERROR"  # 严重错误，必须修复
    WARNING = "WARNING"  # 警告，建议修复
    INFO = "INFO"  # 信息提示


@dataclass
class ValidationResult:
    """验证结果"""
    level: ValidationLevel
    field: str
    message: str
    current_value: Any = None
    suggested_value: Any = None
    fix_command: Optional[str] = None


@dataclass
class ConfigValidationReport:
    """配置验证报告"""
    results: List[ValidationResult] = field(default_factory=list)
    is_valid: bool = True
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0

    def add_result(self, result: ValidationResult):
        """添加验证结果"""
        self.results.append(result)

        if result.level == ValidationLevel.ERROR:
            self.is_valid = False
            self.error_count += 1
        elif result.level == ValidationLevel.WARNING:
            self.warning_count += 1
        else:
            self.info_count += 1

    def get_summary(self) -> str:
        """获取验证摘要"""
        total = len(self.results)
        if self.is_valid:
            return f"✅ 配置验证通过 (共检查 {total} 项)"
        else:
            return f"❌ 配置验证失败 (错误: {self.error_count}, 警告: {self.warning_count}, 信息: {self.info_count})"

    def print_report(self):
        """打印验证报告"""
        print(f"\n{self.get_summary()}")
        print("="*60)

        if self.error_count > 0:
            print("\n🚨 严重错误 (必须修复):")
            for result in self.results:
                if result.level == ValidationLevel.ERROR:
                    print(f"   ❌ {result.field}: {result.message}")
                    if result.suggested_value:
                        print(f"      💡 建议值: {result.suggested_value}")
                    if result.fix_command:
                        print(f"      🔧 修复命令: {result.fix_command}")

        if self.warning_count > 0:
            print("\n⚠️  警告 (建议修复):")
            for result in self.results:
                if result.level == ValidationLevel.WARNING:
                    print(f"   ⚠️  {result.field}: {result.message}")
                    if result.suggested_value:
                        print(f"      💡 建议值: {result.suggested_value}")

        if self.info_count > 0:
            print("\nℹ️  信息提示:")
            for result in self.results:
                if result.level == ValidationLevel.INFO:
                    print(f"   ℹ️  {result.field}: {result.message}")

        print("="*60)


class ConfigValidator:
    """配置验证器"""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.env_file = self.project_root / ".env"
        self.config_file = self.project_root / "config.json"

        # 验证规则
        self.validation_rules = {
            # qBittorrent配置
            'QBT_HOST': {
                'required': True,
                'type': str,
                'pattern': r'^[a-zA-Z0-9.-]+$',
                'description': 'qBittorrent主机地址'
            },
            'QBT_PORT': {
                'required': True,
                'type': int,
                'min_value': 1,
                'max_value': 65535,
                'description': 'qBittorrent端口'
            },
            'QBT_USERNAME': {
                'required': True,
                'type': str,
                'min_length': 1,
                'description': 'qBittorrent用户名'
            },
            'QBT_PASSWORD': {
                'required': True,
                'type': str,
                'min_length': 4,
                'description': 'qBittorrent密码'
            },

            # AI配置
            'AI_PROVIDER': {
                'required': False,
                'type': str,
                'choices': ['deepseek', 'openai', 'none'],
                'default': 'deepseek',
                'description': 'AI服务提供商'
            },
            'AI_API_KEY': {
                'required': False,
                'type': str,
                'conditional_required': lambda env: env.get('AI_PROVIDER', 'none') != 'none',
                'min_length': 10,
                'description': 'AI API密钥'
            },
            'AI_MODEL': {
                'required': False,
                'type': str,
                'default': 'deepseek-chat',
                'description': 'AI模型名称'
            },

            # 监控配置
            'MONITOR_CHECK_INTERVAL': {
                'required': False,
                'type': float,
                'min_value': 0.1,
                'max_value': 60.0,
                'default': 1.0,
                'description': '监控检查间隔(秒)'
            },
            'MONITOR_ADAPTIVE_INTERVAL': {
                'required': False,
                'type': bool,
                'default': True,
                'description': '启用自适应间隔'
            },
            'MONITOR_MIN_INTERVAL': {
                'required': False,
                'type': float,
                'min_value': 0.1,
                'max_value': 5.0,
                'default': 0.1,
                'description': '最小检查间隔(秒)'
            },
            'MONITOR_MAX_INTERVAL': {
                'required': False,
                'type': float,
                'min_value': 1.0,
                'max_value': 60.0,
                'default': 5.0,
                'description': '最大检查间隔(秒)'
            },

            # 缓存配置
            'CACHE_ENABLE_DUPLICATE_FILTER': {
                'required': False,
                'type': bool,
                'default': True,
                'description': '启用重复过滤器'
            },
            'CACHE_SIZE': {
                'required': False,
                'type': int,
                'min_value': 100,
                'max_value': 10000,
                'default': 1000,
                'description': '缓存大小'
            },
            'CACHE_TTL_SECONDS': {
                'required': False,
                'type': int,
                'min_value': 60,
                'max_value': 86400,
                'default': 300,
                'description': '缓存过期时间(秒)'
            },

            # 日志配置
            'LOG_LEVEL': {
                'required': False,
                'type': str,
                'choices': ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                'default': 'INFO',
                'description': '日志级别'
            },
            'LOG_FILE': {
                'required': False,
                'type': str,
                'default': 'logs/qbittorrent-monitor.log',
                'description': '日志文件路径'
            },

            # 性能配置
            'PERFORMANCE_FAST_START': {
                'required': False,
                'type': bool,
                'default': True,
                'description': '启用快速启动'
            },
            'PERFORMANCE_MEMORY_POOL': {
                'required': False,
                'type': bool,
                'default': True,
                'description': '启用内存池'
            },
            'PERFORMANCE_BATCH_SIZE': {
                'required': False,
                'type': int,
                'min_value': 1,
                'max_value': 100,
                'default': 10,
                'description': '批量处理大小'
            },

            # Web界面配置
            'WEB_ENABLED': {
                'required': False,
                'type': bool,
                'default': False,
                'description': '启用Web界面'
            },
            'WEB_HOST': {
                'required': False,
                'type': str,
                'default': '0.0.0.0',
                'description': 'Web界面主机'
            },
            'WEB_PORT': {
                'required': False,
                'type': int,
                'min_value': 1,
                'max_value': 65535,
                'default': 8081,
                'description': 'Web界面端口'
            },

            # 通知配置
            'NOTIFICATIONS_ENABLED': {
                'required': False,
                'type': bool,
                'default': False,
                'description': '启用通知'
            }
        }

    def load_environment(self) -> Dict[str, str]:
        """加载环境变量"""
        env_config = {}

        # 从.env文件加载
        if self.env_file.exists():
            with open(self.env_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        try:
                            key, value = line.split('=', 1)
                            env_config[key.strip()] = value.strip()
                        except ValueError:
                            logger.warning(f"环境变量格式错误 (行{line_num}): {line}")

        # 从系统环境变量加载
        for key, value in os.environ.items():
            if key.startswith(('QBT_', 'AI_', 'MONITOR_', 'CACHE_', 'LOG_', 'PERFORMANCE_', 'WEB_', 'NOTIFICATIONS_', 'CRAWLER_')):
                env_config[key] = value

        return env_config

    def convert_value(self, value: str, target_type: type) -> Any:
        """类型转换"""
        if target_type == bool:
            return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
        elif target_type == int:
            try:
                return int(value)
            except ValueError:
                raise ValueError(f"无法转换为整数: {value}")
        elif target_type == float:
            try:
                return float(value)
            except ValueError:
                raise ValueError(f"无法转换为浮点数: {value}")
        else:
            return value

    def validate_field(self, field_name: str, value: str, env_config: Dict[str, str]) -> ValidationResult:
        """验证单个字段"""
        rules = self.validation_rules.get(field_name, {})

        # 检查必需字段
        if rules.get('required', False):
            if not value:
                return ValidationResult(
                    level=ValidationLevel.ERROR,
                    field=field_name,
                    message=f"缺少必需的配置: {rules.get('description', field_name)}",
                    suggested_value=rules.get('default')
                )

        # 检查条件必需字段
        conditional_required = rules.get('conditional_required')
        if conditional_required and callable(conditional_required):
            if not value and conditional_required(env_config):
                return ValidationResult(
                    level=ValidationLevel.ERROR,
                    field=field_name,
                    message=f"当前配置下此字段为必需: {rules.get('description', field_name)}",
                    suggested_value=rules.get('default')
                )

        # 如果值为空且不是必需的，使用默认值
        if not value and 'default' in rules:
            value = str(rules['default'])

        # 类型检查和转换
        target_type = rules.get('type', str)
        try:
            converted_value = self.convert_value(value, target_type)
        except ValueError as e:
            return ValidationResult(
                level=ValidationLevel.ERROR,
                field=field_name,
                message=f"类型错误: {e}",
                current_value=value,
                suggested_value=str(rules.get('default', ''))
            )

        # 验证选择项
        if 'choices' in rules:
            choices = rules['choices']
            if converted_value not in choices:
                return ValidationResult(
                    level=ValidationLevel.ERROR,
                    field=field_name,
                    message=f"无效值，可选值: {choices}",
                    current_value=converted_value,
                    suggested_value=rules.get('default', choices[0])
                )

        # 正则表达式验证
        if 'pattern' in rules:
            pattern = rules['pattern']
            if not re.match(pattern, str(converted_value)):
                return ValidationResult(
                    level=ValidationLevel.ERROR,
                    field=field_name,
                    message=f"格式不匹配，要求: {pattern}",
                    current_value=converted_value
                )

        # 数值范围验证
        if isinstance(converted_value, (int, float)):
            if 'min_value' in rules and converted_value < rules['min_value']:
                return ValidationResult(
                    level=ValidationLevel.ERROR,
                    field=field_name,
                    message=f"值太小，最小值: {rules['min_value']}",
                    current_value=converted_value,
                    suggested_value=rules['min_value']
                )

            if 'max_value' in rules and converted_value > rules['max_value']:
                return ValidationResult(
                    level=ValidationLevel.ERROR,
                    field=field_name,
                    message=f"值太大，最大值: {rules['max_value']}",
                    current_value=converted_value,
                    suggested_value=rules['max_value']
                )

        # 字符串长度验证
        if isinstance(converted_value, str):
            if 'min_length' in rules and len(converted_value) < rules['min_length']:
                return ValidationResult(
                    level=ValidationLevel.ERROR,
                    field=field_name,
                    message=f"长度太短，最小长度: {rules['min_length']}",
                    current_value=converted_value
                )

        # 特殊验证逻辑
        if field_name == 'AI_API_KEY' and converted_value:
            if converted_value == 'your_deepseek_api_key_here' or converted_value == 'your_api_key_here':
                return ValidationResult(
                    level=ValidationLevel.WARNING,
                    field=field_name,
                    message="请设置真实的API密钥",
                    current_value=converted_value
                )

        # 性能建议
        if field_name == 'MONITOR_CHECK_INTERVAL' and converted_value < 0.5:
            return ValidationResult(
                level=ValidationLevel.WARNING,
                field=field_name,
                message="检查间隔过短可能影响系统性能",
                current_value=converted_value,
                suggested_value=1.0
            )

        # 端口冲突检查
        if field_name in ['QBT_PORT', 'WEB_PORT']:
            if self._is_port_in_use(converted_value):
                return ValidationResult(
                    level=ValidationLevel.WARNING,
                    field=field_name,
                    message=f"端口 {converted_value} 可能已被占用",
                    current_value=converted_value
                )

        return ValidationResult(
            level=ValidationLevel.INFO,
            field=field_name,
            message="配置有效",
            current_value=converted_value
        )

    def _is_port_in_use(self, port: int) -> bool:
        """检查端口是否被占用"""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                return s.connect_ex(('localhost', port)) == 0
        except:
            return False

    def validate_all(self) -> ConfigValidationReport:
        """验证所有配置"""
        report = ConfigValidationReport()
        env_config = self.load_environment()

        logger.info(f"开始验证配置，共 {len(self.validation_rules)} 项")

        for field_name, rules in self.validation_rules.items():
            value = env_config.get(field_name, '')

            try:
                result = self.validate_field(field_name, value, env_config)
                report.add_result(result)
            except Exception as e:
                logger.error(f"验证字段 {field_name} 时出错: {e}")
                report.add_result(ValidationResult(
                    level=ValidationLevel.ERROR,
                    field=field_name,
                    message=f"验证失败: {e}",
                    current_value=value
                ))

        # 检查缺失的配置文件
        if not self.env_file.exists():
            report.add_result(ValidationResult(
                level=ValidationLevel.WARNING,
                field='.env',
                message="环境变量文件不存在",
                fix_command="python scripts/environment_manager.py"
            ))

        return report

    def fix_config_interactive(self, report: ConfigValidationReport) -> bool:
        """交互式修复配置"""
        if report.is_valid:
            print("✅ 配置无需修复")
            return True

        print("\n🔧 开始交互式配置修复...")

        # 读取当前环境配置
        env_config = self.load_environment()

        # 处理所有错误和警告
        for result in report.results:
            if result.level in [ValidationLevel.ERROR, ValidationLevel.WARNING]:
                print(f"\n📝 {result.field}")
                print(f"   问题: {result.message}")
                if result.current_value:
                    print(f"   当前值: {result.current_value}")
                if result.suggested_value:
                    print(f"   建议值: {result.suggested_value}")

                # 询问用户是否修复
                choice = input(f"   是否修复? (y/n/s 跳过) [y]: ").strip().lower()

                if choice in ['', 'y', 'yes']:
                    if result.suggested_value:
                        new_value = str(result.suggested_value)
                    else:
                        new_value = input(f"   请输入新的值: ").strip()

                    if new_value:
                        env_config[result.field] = new_value
                        print(f"   ✅ 已更新: {result.field} = {new_value}")
                elif choice in ['s', 'skip']:
                    print(f"   ⏭️  跳过: {result.field}")
                else:
                    print(f"   ❌ 取消修复")

        # 保存修复后的配置
        try:
            self._save_env_file(env_config)
            print("\n✅ 配置修复完成，已保存到 .env 文件")
            return True
        except Exception as e:
            print(f"\n❌ 保存配置失败: {e}")
            return False

    def _save_env_file(self, env_config: Dict[str, str]):
        """保存环境变量文件"""
        with open(self.env_file, 'w', encoding='utf-8') as f:
            # 写入注释头
            f.write("# qBittorrent 剪贴板监控器配置文件\n")
            f.write("# 自动生成，请根据需要修改\n\n")

            # 按组写入配置
            groups = {
                'qBittorrent': ['QBT_HOST', 'QBT_PORT', 'QBT_USERNAME', 'QBT_PASSWORD'],
                'AI': ['AI_PROVIDER', 'AI_API_KEY', 'AI_MODEL'],
                '监控': ['MONITOR_CHECK_INTERVAL', 'MONITOR_ADAPTIVE_INTERVAL', 'MONITOR_MIN_INTERVAL', 'MONITOR_MAX_INTERVAL'],
                '缓存': ['CACHE_ENABLE_DUPLICATE_FILTER', 'CACHE_SIZE', 'CACHE_TTL_SECONDS'],
                '日志': ['LOG_LEVEL', 'LOG_FILE'],
                '性能': ['PERFORMANCE_FAST_START', 'PERFORMANCE_MEMORY_POOL', 'PERFORMANCE_BATCH_SIZE'],
                'Web界面': ['WEB_ENABLED', 'WEB_HOST', 'WEB_PORT'],
                '通知': ['NOTIFICATIONS_ENABLED']
            }

            for group_name, fields in groups.items():
                f.write(f"# {group_name}配置\n")
                for field in fields:
                    if field in env_config:
                        f.write(f"{field}={env_config[field]}\n")
                f.write("\n")

    def generate_config_template(self) -> str:
        """生成配置模板"""
        template = "# qBittorrent 剪贴板监控器配置模板\n\n"

        groups = {
            'qBittorrent': ['QBT_HOST', 'QBT_PORT', 'QBT_USERNAME', 'QBT_PASSWORD'],
            'AI': ['AI_PROVIDER', 'AI_API_KEY', 'AI_MODEL'],
            '监控': ['MONITOR_CHECK_INTERVAL', 'MONITOR_ADAPTIVE_INTERVAL', 'MONITOR_MIN_INTERVAL', 'MONITOR_MAX_INTERVAL'],
            '缓存': ['CACHE_ENABLE_DUPLICATE_FILTER', 'CACHE_SIZE', 'CACHE_TTL_SECONDS'],
            '日志': ['LOG_LEVEL', 'LOG_FILE'],
            '性能': ['PERFORMANCE_FAST_START', 'PERFORMANCE_MEMORY_POOL', 'PERFORMANCE_BATCH_SIZE'],
            'Web界面': ['WEB_ENABLED', 'WEB_HOST', 'WEB_PORT'],
            '通知': ['NOTIFICATIONS_ENABLED']
        }

        for group_name, fields in groups.items():
            template += f"# {group_name}配置\n"
            for field in fields:
                rules = self.validation_rules.get(field, {})
                default_value = rules.get('default', '')
                description = rules.get('description', '')

                if default_value:
                    template += f"{field}={default_value}  # {description}\n"
                else:
                    template += f"{field}=  # {description}\n"
            template += "\n"

        return template


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="配置验证器")
    parser.add_argument("--fix", action="store_true", help="交互式修复配置")
    parser.add_argument("--template", action="store_true", help="生成配置模板")
    parser.add_argument("--output", type=str, help="输出文件路径")

    args = parser.parse_args()

    validator = ConfigValidator()

    if args.template:
        template = validator.generate_config_template()
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(template)
            print(f"配置模板已生成: {args.output}")
        else:
            print(template)
        return

    # 运行验证
    report = validator.validate_all()
    report.print_report()

    # 如果需要修复
    if args.fix and not report.is_valid:
        success = validator.fix_config_interactive(report)
        if success:
            print("\n🎉 配置修复完成！")
        else:
            print("\n❌ 配置修复失败！")

    # 返回状态码
    sys.exit(0 if report.is_valid else 1)


if __name__ == "__main__":
    main()