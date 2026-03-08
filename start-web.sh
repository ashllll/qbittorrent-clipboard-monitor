#!/bin/bash
# qBittorrent Clipboard Monitor Web 启动脚本

CONFIG_FILE="$HOME/.config/qb-monitor/config.json"

echo "=================================================="
echo "qBittorrent Clipboard Monitor - Web 管理界面"
echo "=================================================="
echo ""

# 检查配置文件
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 配置文件不存在: $CONFIG_FILE"
    exit 1
fi

# 显示当前配置
echo "当前配置:"
echo "  qBittorrent 地址: $(grep -o '"host": "[^"]*"' "$CONFIG_FILE" | head -1 | cut -d'"' -f4):$(grep -o '"port": [0-9]*' "$CONFIG_FILE" | head -1 | grep -o '[0-9]*')"
echo "  用户名: $(grep -o '"username": "[^"]*"' "$CONFIG_FILE" | head -1 | cut -d'"' -f4)"
echo ""

# 询问密码
read -s -p "请输入 qBittorrent 密码: " QBIT_PASS
echo ""

if [ -z "$QBIT_PASS" ]; then
    echo "❌ 密码不能为空"
    exit 1
fi

# 更新配置文件中的密码
python3 << PYTHON
import json
config_path = "$CONFIG_FILE"
with open(config_path, 'r') as f:
    data = json.load(f)
data['qbittorrent']['password'] = "$QBIT_PASS"
with open(config_path, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("✓ 密码已保存到配置文件")
PYTHON

echo ""
echo "=================================================="
echo "启动 Web 管理界面..."
echo "访问地址: http://127.0.0.1:8888"
echo "=================================================="
echo ""

# 启动程序
python3 run.py --web --web-port 8888 --log-level INFO
