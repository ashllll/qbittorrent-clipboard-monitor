#!/usr/bin/env python3
"""
配置文档生成工具

从Pydantic模型自动生成配置文档，包括:
- Markdown配置文档
- JSON Schema
- 环境变量映射表
- 配置示例

用法:
    python scripts/config/generate_docs.py --output docs/config/
    python scripts/config/generate_docs.py --format json-schema
    python scripts/config/generate_docs.py --format markdown
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, get_type_hints
from dataclasses import dataclass, field
from inspect import getdoc

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from pydantic import BaseModel, Field
    from qbittorrent_monitor.config import (
        AppConfig, QBittorrentConfig, DeepSeekConfig,
        CategoryConfig, WebCrawlerConfig, NotificationConfig,
        ConsoleNotificationConfig, PathMappingRule
    )
    HAS_MODELS = True
except ImportError as e:
    print(f"警告: 无法导入Pydantic模型: {e}")
    HAS_MODELS = False


@dataclass
class ConfigField:
    """配置字段信息"""
    name: str
    type: str
    required: bool
    default: Any
    description: str
    examples: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    alias: Optional[str] = None
    env_var: Optional[str] = None


@dataclass
class ConfigSection:
    """配置节信息"""
    name: str
    description: str
    fields: List[ConfigField] = field(default_factory=list)
    required: bool = False


class SchemaGenerator:
    """JSON Schema生成器"""

    TYPE_MAPPING = {
        'str': 'string',
        'int': 'integer',
        'float': 'number',
        'bool': 'boolean',
        'list': 'array',
        'dict': 'object',
        'NoneType': 'null',
    }

    def __init__(self):
        self.definitions: Dict[str, Any] = {}

    def generate(self, model_class: Type[BaseModel], title: str = None) -> Dict[str, Any]:
        """生成JSON Schema"""
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": f"https://github.com/ashllll/qbittorrent-clipboard-monitor/{model_class.__name__.lower()}.schema.json",
            "title": title or model_class.__name__,
            "description": getdoc(model_class) or "",
            "type": "object",
        }

        properties = {}
        required = []

        # 获取模型字段
        if hasattr(model_class, 'model_fields'):
            # Pydantic v2
            fields = model_class.model_fields
        else:
            # Pydantic v1
            fields = model_class.__fields__

        for field_name, field_info in fields.items():
            field_schema = self._get_field_schema(field_info, field_name)
            properties[field_name] = field_schema

            # 检查是否必需
            if self._is_required(field_info):
                required.append(field_name)

        schema['properties'] = properties
        if required:
            schema['required'] = required

        if self.definitions:
            schema['definitions'] = self.definitions

        return schema

    def _get_field_schema(self, field_info: Any, field_name: str) -> Dict[str, Any]:
        """获取字段的Schema"""
        schema: Dict[str, Any] = {}

        # 获取字段类型和描述
        if hasattr(field_info, 'annotation'):
            # Pydantic v2
            field_type = field_info.annotation
            description = field_info.description or ""
            default = field_info.default
        else:
            # Pydantic v1
            field_type = field_info.outer_type_
            description = field_info.field_info.description or ""
            default = field_info.default

        # 处理Optional类型
        is_optional = False
        origin = getattr(field_type, '__origin__', None)
        if origin is not None:
            if origin.__name__ == 'Union' if hasattr(origin, '__name__') else str(origin) == 'typing.Union':
                args = getattr(field_type, '__args__', ())
                if type(None) in args:
                    is_optional = True
                    # 获取非None类型
                    for arg in args:
                        if arg is not type(None):
                            field_type = arg
                            break

        # 映射类型
        type_name = self._get_type_name(field_type)
        schema['type'] = type_name

        if is_optional:
            schema['type'] = [type_name, 'null']

        # 添加描述
        if description:
            schema['description'] = description

        # 添加默认值
        if default is not None and default != ...:
            if isinstance(default, (str, int, float, bool)):
                schema['default'] = default
            elif isinstance(default, list):
                schema['default'] = default
            elif isinstance(default, dict):
                schema['default'] = default

        # 处理特殊类型
        if hasattr(field_type, '__origin__') and field_type.__origin__ is list:
            args = getattr(field_type, '__args__', ())
            if args:
                item_type = args[0]
                if hasattr(item_type, 'model_fields') or hasattr(item_type, '__fields__'):
                    # 列表项是模型
                    item_schema = self._get_model_ref(item_type)
                    schema['items'] = item_schema
                else:
                    schema['items'] = {'type': self._get_type_name(item_type)}

        # 处理嵌套模型
        if hasattr(field_type, 'model_fields') or hasattr(field_type, '__fields__'):
            schema = self._get_model_ref(field_type)
            if description:
                schema['description'] = description

        return schema

    def _get_type_name(self, field_type: Any) -> str:
        """获取类型名称"""
        if hasattr(field_type, '__name__'):
            name = field_type.__name__
            return self.TYPE_MAPPING.get(name, 'string')

        origin = getattr(field_type, '__origin__', None)
        if origin is not None:
            if hasattr(origin, '__name__'):
                name = origin.__name__
                if name in ('list', 'List'):
                    return 'array'
                elif name in ('dict', 'Dict'):
                    return 'object'

        return 'string'

    def _is_required(self, field_info: Any) -> bool:
        """检查字段是否必需"""
        if hasattr(field_info, 'is_required'):
            return field_info.is_required()
        elif hasattr(field_info, 'required'):
            return field_info.required
        return False

    def _get_model_ref(self, model_class: Type[BaseModel]) -> Dict[str, Any]:
        """获取模型引用"""
        model_name = model_class.__name__

        if model_name not in self.definitions:
            self.definitions[model_name] = {}  # 占位避免递归

            properties = {}
            required = []

            if hasattr(model_class, 'model_fields'):
                fields = model_class.model_fields
            else:
                fields = model_class.__fields__

            for field_name, field_info in fields.items():
                properties[field_name] = self._get_field_schema(field_info, field_name)
                if self._is_required(field_info):
                    required.append(field_name)

            self.definitions[model_name] = {
                'type': 'object',
                'description': getdoc(model_class) or '',
                'properties': properties,
            }
            if required:
                self.definitions[model_name]['required'] = required

        return {'$ref': f'#/definitions/{model_name}'}


class MarkdownGenerator:
    """Markdown文档生成器"""

    def __init__(self):
        self.sections: List[ConfigSection] = []

    def add_section(self, section: ConfigSection):
        """添加配置节"""
        self.sections.append(section)

    def generate(self, title: str = "配置参考") -> str:
        """生成Markdown文档"""
        lines = [
            f"# {title}",
            "",
            "> **注意**: 本文档由 `scripts/config/generate_docs.py` 自动生成",
            "> **更新时间**: " + self._get_current_time(),
            "",
            "---",
            "",
            "## 目录",
            "",
        ]

        # 生成目录
        for section in self.sections:
            anchor = section.name.lower().replace(' ', '-')
            lines.append(f"- [{section.name}](#{anchor})")

        lines.append("")

        # 生成各节内容
        for section in self.sections:
            lines.extend(self._generate_section(section))

        return '\n'.join(lines)

    def _generate_section(self, section: ConfigSection) -> List[str]:
        """生成配置节内容"""
        lines = [
            "",
            f"## {section.name}",
            "",
            section.description,
            "",
        ]

        if section.fields:
            # 生成表格
            lines.extend([
                "| 配置项 | 类型 | 必填 | 默认值 | 说明 |",
                "|--------|------|------|--------|------|",
            ])

            for field in section.fields:
                required = "✅" if field.required else "❌"
                default = self._format_default(field.default)
                description = field.description.replace('\n', ' ')
                lines.append(
                    f"| `{field.name}` | {field.type} | {required} | {default} | {description} |"
                )

        return lines

    def _format_default(self, default: Any) -> str:
        """格式化默认值"""
        if default is None or default == ...:
            return "-"
        if isinstance(default, str):
            if len(default) > 30:
                return f'`{default[:27]}...`'
            return f'`{default}`'
        if isinstance(default, (list, dict)):
            return f'`{json.dumps(default, ensure_ascii=False)[:30]}...`'
        return f'`{default}`'

    def _get_current_time(self) -> str:
        """获取当前时间"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class ConfigDocsGenerator:
    """配置文档生成器"""

    ENV_MAPPINGS = {
        'qbittorrent.host': 'QBT_HOST',
        'qbittorrent.port': 'QBT_PORT',
        'qbittorrent.username': 'QBT_USERNAME',
        'qbittorrent.password': 'QBT_PASSWORD',
        'qbittorrent.use_https': 'QBT_USE_HTTPS',
        'qbittorrent.verify_ssl': 'QBT_VERIFY_SSL',
        'deepseek.api_key': 'DEEPSEEK_API_KEY',
        'deepseek.base_url': 'DEEPSEEK_BASE_URL',
        'deepseek.model': 'AI_MODEL',
        'deepseek.timeout': 'DEEPSEEK_TIMEOUT',
        'deepseek.max_retries': 'DEEPSEEK_MAX_RETRIES',
        'log_level': 'LOG_LEVEL',
        'log_file': 'LOG_FILE',
        'check_interval': 'CHECK_INTERVAL',
        'hot_reload': 'HOT_RELOAD',
        'proxy': 'PROXY',
    }

    def __init__(self):
        self.schema_generator = SchemaGenerator()
        self.markdown_generator = MarkdownGenerator()

    def generate_all(self, output_dir: Path):
        """生成所有文档"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成JSON Schema
        if HAS_MODELS:
            self._generate_json_schema(output_dir / 'schema')

            # 生成Markdown文档
            self._generate_markdown_docs(output_dir)

            # 生成环境变量映射
            self._generate_env_mapping(output_dir)

            # 生成配置示例
            self._generate_examples(output_dir)

        print(f"✅ 文档已生成到: {output_dir}")

    def _generate_json_schema(self, schema_dir: Path):
        """生成JSON Schema"""
        schema_dir.mkdir(exist_ok=True)

        # 主配置Schema
        schema = self.schema_generator.generate(AppConfig, "qBittorrent剪贴板监控器配置")

        with open(schema_dir / 'config.schema.json', 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)

        print(f"  📄 {schema_dir / 'config.schema.json'}")

    def _generate_markdown_docs(self, output_dir: Path):
        """生成Markdown文档"""
        # 解析模型生成配置节
        sections = self._parse_models()
        for section in sections:
            self.markdown_generator.add_section(section)

        markdown = self.markdown_generator.generate("配置参考手册（自动生成）")

        with open(output_dir / 'CONFIG_REFERENCE_AUTO.md', 'w', encoding='utf-8') as f:
            f.write(markdown)

        print(f"  📄 {output_dir / 'CONFIG_REFERENCE_AUTO.md'}")

    def _parse_models(self) -> List[ConfigSection]:
        """解析Pydantic模型为配置节"""
        sections = []

        model_sections = [
            ('qbittorrent', QBittorrentConfig, 'qBittorrent连接配置'),
            ('deepseek', DeepSeekConfig, 'DeepSeek AI配置'),
            ('categories', CategoryConfig, '分类配置（单分类示例）'),
            ('web_crawler', WebCrawlerConfig, '网页爬虫配置'),
            ('notifications', NotificationConfig, '通知配置'),
        ]

        for prefix, model_class, description in model_sections:
            section = ConfigSection(
                name=prefix.replace('_', ' ').title(),
                description=description,
                required=prefix in ['qbittorrent', 'deepseek', 'categories']
            )

            # 解析字段
            if hasattr(model_class, 'model_fields'):
                fields = model_class.model_fields
            else:
                fields = model_class.__fields__

            for field_name, field_info in fields.items():
                field = self._parse_field(field_name, field_info, prefix)
                section.fields.append(field)

            sections.append(section)

        return sections

    def _parse_field(self, name: str, field_info: Any, prefix: str) -> ConfigField:
        """解析字段信息"""
        if hasattr(field_info, 'annotation'):
            # Pydantic v2
            field_type = field_info.annotation
            description = field_info.description or ""
            default = field_info.default
            is_required = field_info.is_required() if hasattr(field_info, 'is_required') else False
        else:
            # Pydantic v1
            field_type = field_info.outer_type_
            description = field_info.field_info.description or ""
            default = field_info.default
            is_required = field_info.required

        # 获取类型字符串
        type_str = self._get_type_str(field_type)

        # 构建配置路径
        config_path = f"{prefix}.{name}" if prefix else name

        # 查找环境变量映射
        env_var = self.ENV_MAPPINGS.get(config_path)

        return ConfigField(
            name=name,
            type=type_str,
            required=is_required,
            default=default if default != ... else None,
            description=description,
            env_var=env_var
        )

    def _get_type_str(self, field_type: Any) -> str:
        """获取类型字符串表示"""
        if hasattr(field_type, '__name__'):
            return field_type.__name__

        origin = getattr(field_type, '__origin__', None)
        if origin is not None:
            args = getattr(field_type, '__args__', ())
            if args:
                if hasattr(origin, '__name__'):
                    origin_name = origin.__name__
                else:
                    origin_name = str(origin).replace('typing.', '')
                arg_names = [getattr(a, '__name__', str(a)) for a in args]
                return f"{origin_name}[{', '.join(arg_names)}]"

        return str(field_type).replace('typing.', '')

    def _generate_env_mapping(self, output_dir: Path):
        """生成环境变量映射文档"""
        lines = [
            "# 环境变量映射表（自动生成）",
            "",
            "| 环境变量 | 配置路径 | 类型 | 默认值 | 说明 |",
            "|----------|----------|------|--------|------|",
        ]

        for config_path, env_var in sorted(self.ENV_MAPPINGS.items()):
            lines.append(f"| `{env_var}` | `{config_path}` | - | - | - |")

        with open(output_dir / 'ENV_MAPPING_AUTO.md', 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"  📄 {output_dir / 'ENV_MAPPING_AUTO.md'}")

    def _generate_examples(self, output_dir: Path):
        """生成配置示例"""
        examples_dir = output_dir / 'examples'
        examples_dir.mkdir(exist_ok=True)

        from qbittorrent_monitor.config import ConfigTemplate

        templates = {
            'config.example.json': ConfigTemplate.get_development_template,
            'config.production.json': ConfigTemplate.get_production_template,
            'config.testing.json': ConfigTemplate.get_testing_template,
        }

        for filename, template_func in templates.items():
            template = template_func()

            # 添加注释
            example = {
                "_comment": f"{filename.replace('config.', '').replace('.json', '').title()} Environment Configuration",
                **template
            }

            with open(examples_dir / filename, 'w', encoding='utf-8') as f:
                json.dump(example, f, indent=4, ensure_ascii=False)

            print(f"  📄 {examples_dir / filename}")


def main():
    parser = argparse.ArgumentParser(
        description='配置文档生成工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 生成所有文档
  python generate_docs.py --output docs/config/

  # 仅生成JSON Schema
  python generate_docs.py --format json-schema --output docs/config/schema/

  # 仅生成Markdown文档
  python generate_docs.py --format markdown --output docs/config/
        '''
    )

    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=PROJECT_ROOT / 'docs' / 'config',
        help='输出目录'
    )

    parser.add_argument(
        '--format',
        choices=['all', 'json-schema', 'markdown'],
        default='all',
        help='输出格式'
    )

    args = parser.parse_args()

    if not HAS_MODELS:
        print("❌ 无法导入Pydantic模型，请确保安装了所有依赖")
        print("   运行: pip install pydantic")
        sys.exit(1)

    generator = ConfigDocsGenerator()

    if args.format == 'all':
        generator.generate_all(args.output)
    elif args.format == 'json-schema':
        schema_dir = args.output / 'schema'
        schema_dir.mkdir(parents=True, exist_ok=True)
        generator._generate_json_schema(schema_dir)
    elif args.format == 'markdown':
        generator._generate_markdown_docs(args.output)

    print("\n✅ 文档生成完成!")


if __name__ == '__main__':
    main()
