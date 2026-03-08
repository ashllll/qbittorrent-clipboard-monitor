#!/usr/bin/env python3
"""更新保存路径为 NAS 实际路径"""

import json
import os

config_path = os.path.expanduser('~/.config/qb-monitor/config.json')

with open(config_path, 'r') as f:
    config = json.load(f)

print("="*50)
print("当前保存路径配置")
print("="*50)
for name, cat in config['categories'].items():
    print(f"  {name}: {cat['save_path']}")

print()
print("="*50)
print("常见 NAS 路径示例")
print("="*50)
print("""
1. 群晖 DSM:
   /volume1/downloads/movies
   
2. QNAP:
   /share/Download/movies
   
3. 自定义:
   /mnt/data/downloads/movies
   /opt/downloads/movies
   /home/user/downloads/movies
""")

print()
new_base = input("请输入 NAS 上的基础下载路径 (直接回车保持不变): ").strip()

if new_base:
    # 更新所有分类路径
    for name in config['categories']:
        old_path = config['categories'][name]['save_path']
        new_path = f"{new_base}/{name}"
        config['categories'][name]['save_path'] = new_path
        print(f"  {name}: {old_path} -> {new_path}")
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print()
    print("✓ 路径已更新，重启服务后生效")
else:
    print("✓ 保持原有配置")

print()
print("提示：即使路径不存在，qBittorrent 也会自动创建")
