# 故障排除指南

> 📅 **最后更新**: 2025-11-12
> 🎯 **版本**: v2.4.0
> 👥 **适用对象**: 所有用户

---

## 📋 目录

- [快速诊断](#快速诊断)
- [启动问题](#启动问题)
- [连接问题](#连接问题)
- [性能问题](#性能问题)
- [AI分类问题](#AI分类问题)
- [内存和资源问题](#内存和资源问题)
- [日志问题](#日志问题)
- [配置问题](#配置问题)
- [网络问题](#网络问题)
- [系统兼容性问题](#系统兼容性问题)
- [高级故障排除](#高级故障排除)

---

## 🔍 快速诊断

### 1. 一键诊断脚本

```bash
#!/bin/bash
# 保存为 diagnose.sh
echo "=== qBittorrent 剪贴板监控器诊断 ==="

echo -e "\n[1/6] 系统信息:"
python --version
uname -a
free -h

echo -e "\n[2/6] Python环境:"
python scripts/environment_manager.py --check

echo -e "\n[3/6] 配置验证:"
python qbittorrent_monitor/config_validator.py

echo -e "\n[4/6] 端口检查:"
netstat -tlnp | grep -E ":(8080|8090|8091)"

echo -e "\n[5/6] 进程检查:"
ps aux | grep -E "(qbittorrent|python.*start)"

echo -e "\n[6/6] 服务状态:"
systemctl status qbittorrent-nox 2>/dev/null || echo "qBittorrent服务未检测到"

echo -e "\n=== 诊断完成 ==="
```

运行诊断：
```bash
chmod +x diagnose.sh
./diagnose.sh
```

### 2. 自动修复命令

```bash
# 自动修复常见问题
python -c "
import sys
import subprocess
import os

def run_command(cmd, description):
    print(f'执行: {description}')
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f'✅ {description} - 成功')
        else:
            print(f'❌ {description} - 失败: {result.stderr}')
    except Exception as e:
        print(f'❌ {description} - 异常: {e}')

print('=== 自动修复常见问题 ===')

# 1. 重新创建虚拟环境
run_command('python scripts/environment_manager.py --force', '重新创建虚拟环境')

# 2. 重新安装依赖
run_command('pip install -r requirements.txt --upgrade', '升级依赖')

# 3. 验证配置
run_command('python qbittorrent_monitor/config_validator.py --fix', '修复配置')

# 4. 创建必要目录
run_command('mkdir -p logs .cache', '创建必要目录')

# 5. 设置权限
run_command('chmod +x run.sh', '设置启动脚本权限')

print('=== 自动修复完成 ===')
"
```

---

## 🚀 启动问题

### 问题1: ModuleNotFoundError

**错误信息**:
```
ModuleNotFoundError: No module named 'qbittorrent_monitor'
```

**原因**: Python路径配置错误或模块未安装

**解决方案**:
```bash
# 方案1: 使用项目根目录启动
cd /path/to/qbittorrent-clipboard-monitor
python start.py

# 方案2: 设置PYTHONPATH
export PYTHONPATH="/path/to/qbittorrent-clipboard-monitor:$PYTHONPATH"
python start.py

# 方案3: 使用启动脚本
./run.sh

# 方案4: 重新安装
python scripts/environment_manager.py --force
```

### 问题2: 权限拒绝

**错误信息**:
```
PermissionError: [Errno 13] Permission denied: 'logs/qbittorrent-monitor.log'
```

**原因**: 文件权限不足

**解决方案**:
```bash
# 创建必要目录
mkdir -p logs .cache

# 设置正确权限
chmod 755 logs .cache
chmod 644 logs/*.log 2>/dev/null || true

# 如果是systemd服务，检查服务用户
sudo systemctl edit qbittorrent-monitor
# 添加:
# [Service]
# User=your-username
# Group=your-username
```

### 问题3: Python版本不兼容

**错误信息**:
```
SyntaxError: invalid syntax
或
ImportError: cannot import name 'abc' from 'xyz'
```

**原因**: Python版本不匹配

**解决方案**:
```bash
# 检查Python版本
python --version

# 如果版本不兼容，安装正确版本
sudo apt install python3.11 python3.11-venv  # Ubuntu/Debian
sudo yum install python311 python311-pip  # CentOS/RHEL
brew install python@3.11  # macOS

# 创建正确版本的虚拟环境
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows
```

### 问题4: 虚拟环境激活失败

**错误信息**:
```
command not found: activate
或
virtualenv is not installed
```

**解决方案**:
```bash
# 安装virtualenv
pip install virtualenv

# 重新创建虚拟环境
python -m virtualenv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate  # Windows

# 或使用系统venv模块
python -m venv venv --system-site-packages
```

---

## 🔗 连接问题

### 问题1: qBittorrent连接失败

**错误信息**:
```
ConnectionError: Failed to connect to qBittorrent at localhost:8080
```

**诊断步骤**:
```bash
# 1. 检查qBittorrent是否运行
ps aux | grep qbittorrent
systemctl status qbittorrent-nox

# 2. 检查端口是否开放
netstat -tlnp | grep :8080
telnet localhost 8080

# 3. 检查Web API是否启用
curl -I http://localhost:8080

# 4. 检查防火墙
sudo ufw status
sudo iptables -L
```

**解决方案**:
```bash
# 启动qBittorrent
sudo systemctl start qbittorrent-nox
sudo systemctl enable qbittorrent-nox

# 或手动启动
qbittorrent-nox --daemon --webui-port=8080

# 配置Web API
# Web UI -> 工具 -> 选项 -> Web UI -> 勾选"Web用户界面"
```

### 问题2: 认证失败

**错误信息**:
```
QbtAuthError: Authentication failed for qBittorrent
```

**原因**: 用户名或密码错误

**解决方案**:
```bash
# 1. 重置qBittorrent密码
# 编辑配置文件
nano ~/.config/qBittorrent/qBittorrent.ini

# 2. 查找或添加以下配置
[Preferences]
WebUI\\Username=admin
WebUI\\Password=adminadmin

# 3. 重启qBittorrent
sudo systemctl restart qbittorrent-nox

# 4. 更新.env文件
sed -i 's/QBT_USERNAME=.*/QBT_USERNAME=admin/' .env
sed -i 's/QBT_PASSWORD=.*/QBT_PASSWORD=adminadmin/' .env
```

### 问题3: 连接超时

**错误信息**:
```
asyncio.TimeoutError: Connection to qBittorrent timed out
```

**解决方案**:
```bash
# 增加超时时间
echo "QBT_REQUEST_TIMEOUT=60" >> .env

# 检查网络延迟
ping -c 4 localhost

# 优化qBittorrent性能
# Web UI -> 工具 -> 选项 -> 高级 -> 调整性能设置
```

---

## ⚡ 性能问题

### 问题1: CPU使用率过高

**症状**: CPU使用率持续超过80%

**诊断**:
```bash
# 检查CPU使用
top -p $(pgrep -f qbittorrent-monitor)
htop

# 检查监控间隔
grep "MONITOR_CHECK_INTERVAL" .env

# 检查日志频率
tail -f logs/qbittorrent-monitor.log | wc -l
```

**解决方案**:
```bash
# 1. 调整监控间隔
sed -i 's/MONITOR_CHECK_INTERVAL=.*/MONITOR_CHECK_INTERVAL=2.0/' .env

# 2. 启用自适应间隔
echo "MONITOR_ADAPTIVE_INTERVAL=true" >> .env

# 3. 减少AI分类频率
echo "AI_CLASSIFICATION_ENABLED=false" >> .env  # 临时禁用

# 4. 限制并发数
echo "MAX_CONCURRENT_TASKS=5" >> .env
```

### 问题2: 内存泄漏

**症状**: 内存使用持续增长

**诊断**:
```bash
# 监控内存使用
watch -n 5 'ps aux | grep qbittorrent-monitor | grep -v grep'

# 检查内存详情
cat /proc/$(pgrep -f qbittorrent-monitor)/status | grep -E "(VmRSS|VmSize)"
```

**解决方案**:
```bash
# 1. 减少缓存大小
echo "CACHE_SIZE=500" >> .env
echo "CACHE_TTL_SECONDS=300" >> .env

# 2. 启用内存清理
echo "MEMORY_CLEANUP_ENABLED=true" >> .env
echo "MEMORY_CLEANUP_INTERVAL=300" >> .env

# 3. 重启服务
pkill -f qbittorrent-monitor
./run.sh
```

### 问题3: 响应缓慢

**症状**: 操作响应时间超过5秒

**诊断**:
```bash
# 检查系统负载
uptime
iostat -x 1

# 检查网络延迟
ping -c 4 8.8.8.8

# 检查磁盘IO
iotop
```

**解决方案**:
```bash
# 1. 优化数据库（如果有）
sqlite3 .cache/cache.db "VACUUM;"

# 2. 清理日志文件
find logs/ -name "*.log" -mtime +7 -delete

# 3. 调整连接池
echo "QBT_CONNECTION_POOL_SIZE=10" >> .env
```

---

## 🤖 AI分类问题

### 问题1: API密钥错误

**错误信息**:
```
AIApiError: Invalid API key
```

**解决方案**:
```bash
# 1. 检查API密钥格式
echo $AI_API_KEY | head -c 20

# 2. 更新配置
echo "AI_API_KEY=your_actual_api_key" > .env.local
source .env.local

# 3. 测试API连接
curl -H "Authorization: Bearer $AI_API_KEY" \
     https://api.deepseek.com/v1/models
```

### 问题2: API限频

**错误信息**:
```
AIRateLimitError: Rate limit exceeded
```

**解决方案**:
```bash
# 1. 增加重试间隔
echo "AI_RETRY_DELAY=5.0" >> .env

# 2. 减少并发请求
echo "AI_MAX_CONCURRENT=1" >> .env

# 3. 启用缓存
echo "AI_CACHE_ENABLED=true" >> .env
echo "AI_CACHE_TTL=3600" >> .env
```

### 问题3: 网络连接问题

**错误信息**:
```
NetworkError: Failed to connect to AI API
```

**诊断**:
```bash
# 检查网络连接
curl -I https://api.deepseek.com
ping api.deepseek.com

# 检查代理设置
echo $HTTP_PROXY
echo $HTTPS_PROXY

# 检查DNS解析
nslookup api.deepseek.com
```

**解决方案**:
```bash
# 1. 配置代理（如果需要）
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080

# 2. 设置超时
echo "AI_TIMEOUT=30" >> .env

# 3. 使用备用API端点
echo "AI_BASE_URL=https://api.deepseek.com" >> .env
```

---

## 💾 内存和资源问题

### 问题1: 内存不足

**错误信息**:
```
MemoryError: Unable to allocate memory
```

**诊断**:
```bash
# 检查可用内存
free -h
cat /proc/meminfo | grep -E "(MemTotal|MemAvailable)"

# 检查交换空间
swapon --show
```

**解决方案**:
```bash
# 1. 启用交换空间
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 2. 调整进程内存限制
echo "* soft rss 2097152" >> /etc/security/limits.conf
echo "* hard rss 4194304" >> /etc/security/limits.conf

# 3. 优化应用配置
echo "MEMORY_LIMIT_MB=512" >> .env
```

### 问题2: 文件描述符耗尽

**错误信息**:
```
OSError: [Errno 24] Too many open files
```

**诊断**:
```bash
# 检查当前限制
ulimit -n
cat /proc/$(pgrep -f qbittorrent-monitor)/limits | grep "Max open files"

# 检查文件使用
lsof -p $(pgrep -f qbittorrent-monitor) | wc -l
```

**解决方案**:
```bash
# 1. 临时增加限制
ulimit -n 65536

# 2. 永久设置
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# 3. 优化连接池
echo "QBT_CONNECTION_POOL_SIZE=20" >> .env
```

### 问题3: 磁盘空间不足

**错误信息**:
```
OSError: [Errno 28] No space left on device
```

**诊断**:
```bash
# 检查磁盘使用
df -h
du -sh /path/to/qbittorrent-clipboard-monitor

# 检查大文件
find /path/to/qbittorrent-clipboard-monitor -size +100M -exec ls -lh {} \;
```

**解决方案**:
```bash
# 1. 清理日志文件
find logs/ -name "*.log" -mtime +7 -delete
find logs/ -name "*.log" -size +10M -exec truncate -s 10M {} \;

# 2. 清理缓存
rm -rf .cache/*
echo "CACHE_CLEANUP_ENABLED=true" >> .env

# 3. 配置日志轮转
cat > /etc/logrotate.d/qbittorrent-monitor << EOF
/path/to/qbittorrent-clipboard-monitor/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    copytruncate
}
EOF
```

---

## 📝 日志问题

### 问题1: 日志文件无法创建

**错误信息**:
```
PermissionError: [Errno 13] Permission denied: 'logs/qbittorrent-monitor.log'
```

**解决方案**:
```bash
# 创建日志目录
mkdir -p logs
chmod 755 logs

# 检查目录权限
ls -la logs/

# 修复权限
sudo chown -R $USER:$USER logs/
chmod +w logs/
```

### 问题2: 日志文件过大

**症状**: 日志文件超过1GB

**解决方案**:
```bash
# 1. 轮转日志
logrotate -f /etc/logrotate.d/qbittorrent-monitor

# 2. 手动压缩
gzip logs/qbittorrent-monitor.log

# 3. 配置日志级别
echo "LOG_LEVEL=WARNING" >> .env

# 4. 限制日志大小
echo "LOG_MAX_SIZE_MB=100" >> .env
```

### 问题3: 日志格式问题

**症状**: 日志无法正确解析

**解决方案**:
```bash
# 1. 检查日志格式
head -20 logs/qbittorrent-monitor.log

# 2. 重新配置日志格式
cat > logging_config.yaml << EOF
version: 1
formatters:
  standard:
    format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
handlers:
  console:
    class: logging.StreamHandler
    formatter: standard
    stream: ext://sys.stdout
  file:
    class: logging.handlers.RotatingFileHandler
    formatter: standard
    filename: logs/qbittorrent-monitor.log
    maxBytes: 10485760
    backupCount: 5
root:
  level: INFO
  handlers: [console, file]
EOF

echo "LOGGING_CONFIG=logging_config.yaml" >> .env
```

---

## ⚙️ 配置问题

### 问题1: 配置文件解析错误

**错误信息**:
```
ConfigError: Invalid configuration: xxx
```

**诊断**:
```bash
# 验证配置
python qbittorrent_monitor/config_validator.py

# 检查语法
python -c "
import json
import yaml
import os

# 检查.env文件
with open('.env', 'r') as f:
    for i, line in enumerate(f, 1):
        if '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            if not key.strip() or not value.strip():
                print(f'行 {i}: 配置格式错误: {line.strip()}')
"
```

**解决方案**:
```bash
# 1. 重新生成配置文件
cp .env.example .env

# 2. 交互式修复配置
python qbittorrent_monitor/config_validator.py --fix

# 3. 手动编辑配置
nano .env
```

### 问题2: 环境变量未生效

**症状**: 配置更改后未生效

**解决方案**:
```bash
# 1. 重新加载环境变量
source .env

# 2. 重启服务
pkill -f qbittorrent-monitor
./run.sh

# 3. 检查环境变量
env | grep -E "(QBT_|AI_|MONITOR_)"
```

### 问题3: 配置优先级混乱

**症状**: 多个配置源冲突

**诊断**:
```bash
# 检查配置加载顺序
python -c "
import os
from qbittorrent_monitor.config import ConfigManager

config_manager = ConfigManager()
config = config_manager.load_config()
print('配置来源:', config._config_source if hasattr(config, '_config_source') else '未知')
"
```

**解决方案**:
```bash
# 1. 统一配置源
# 删除冲突的配置文件
rm config.json config.yaml

# 2. 使用单一配置文件
echo "CONFIG_SOURCE=env" >> .env

# 3. 验证配置
python qbittorrent_monitor/config_validator.py
```

---

## 🌐 网络问题

### 问题1: 代理配置错误

**错误信息**:
```
ProxyError: Unable to connect to proxy
```

**诊断**:
```bash
# 检查代理设置
echo $HTTP_PROXY
echo $HTTPS_PROXY
echo $NO_PROXY

# 测试代理连接
curl -x http://proxy.company.com:8080 http://example.com
```

**解决方案**:
```bash
# 1. 清除代理设置
unset HTTP_PROXY
unset HTTPS_PROXY
unset NO_PROXY

# 2. 或正确配置代理
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
export NO_PROXY=localhost,127.0.0.1

# 3. 在配置中设置
echo "HTTP_PROXY=http://proxy.company.com:8080" >> .env
echo "HTTPS_PROXY=http://proxy.company.com:8080" >> .env
```

### 问题2: DNS解析失败

**错误信息**:
```
gaierror: [Errno -2] Name or service not known
```

**诊断**:
```bash
# 检查DNS配置
cat /etc/resolv.conf
nslookup api.deepseek.com
dig api.deepseek.com

# 测试网络连接
ping -c 4 8.8.8.8
```

**解决方案**:
```bash
# 1. 更换DNS服务器
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 8.8.4.4" >> /etc/resolv.conf

# 2. 在配置中设置DNS
echo "DNS_SERVERS=8.8.8.8,8.8.4.4" >> .env

# 3. 使用IP地址（临时）
echo "AI_BASE_URL=http://180.76.176.43" >> .env
```

### 问题3: 防火墙阻止连接

**症状**: 网络连接被阻止

**诊断**:
```bash
# 检查防火墙状态
sudo ufw status
sudo iptables -L

# 测试端口连通性
telnet api.deepseek.com 443
nc -zv api.deepseek.com 443
```

**解决方案**:
```bash
# 1. 允许出站HTTPS连接
sudo ufw allow out 443/tcp
sudo iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT

# 2. 配置防火墙规则
sudo ufw allow out to any port 443

# 3. 或使用本地防火墙配置工具
# 根据具体系统配置
```

---

## 🔧 系统兼容性问题

### 问题1: Windows权限问题

**错误信息**:
```
PermissionError: [WinError 5] Access is denied
```

**解决方案**:
```powershell
# PowerShell管理员模式运行
# 1. 检查文件权限
Get-Acl .\logs\qbittorrent-monitor.log | Format-List

# 2. 修复权限
icacls .\logs\qbittorrent-monitor.log /grant "$($env:USERNAME):(OI)(CI)F"

# 3. 以管理员身份运行
Start-Process powershell -Verb RunAs
```

### 问题2: macOS安全限制

**错误信息**:
```
OSError: [Errno 1] Operation not permitted
```

**解决方案**:
```bash
# 1. 授予终端访问权限
# 系统偏好设置 -> 安全性与隐私 -> 隐私 -> 完全磁盘访问权限

# 2. 关闭Gatekeeper检查
sudo spctl --master-disable

# 3. 允许应用运行
xattr -d com.apple.quarantine start.py
```

### 问题3: Linux发行版兼容性

**症状**: 某些命令或依赖不存在

**解决方案**:
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3 python3-pip python3-venv build-essential

# CentOS/RHEL
sudo yum update
sudo yum install -y python3 python3-pip python3-venv gcc gcc-c++

# Arch Linux
sudo pacman -Syu
sudo pacman -S python python-pip python-virtualenv base-devel

# 通用解决方案
python -m pip install --upgrade pip setuptools wheel
```

---

## 🔬 高级故障排除

### 1. 调试模式启动

```bash
# 启用详细日志
export LOG_LEVEL=DEBUG
export DEBUG_MODE=true

# 启动调试模式
python start.py --debug --traceback

# 使用strace跟踪系统调用（Linux）
sudo strace -p $(pgrep -f qbittorrent-monitor) -o debug.log

# 使用ltrace跟踪库调用（Linux）
sudo ltrace -p $(pgrep -f qbittorrent-monitor) -o debug.log
```

### 2. 性能分析

```bash
# CPU性能分析
sudo perf record -p $(pgrep -f qbittorrent-monitor) -g
sudo perf report

# 内存分析
valgrind --tool=memcheck --leak-check=full python start.py

# Python性能分析
python -m cProfile -o profile.stats start.py
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
"
```

### 3. 网络抓包

```bash
# 抓取网络流量（需要root权限）
sudo tcpdump -i any -w capture.pcap host api.deepseek.com or port 8080

# 分析抓包文件
tcpdump -r capture.pcap -A

# 使用Wireshark分析
wireshark capture.pcap
```

### 4. 生成系统报告

```bash
# 生成完整的系统报告
python -c "
import platform
import sys
import os
import subprocess
import json
from datetime import datetime

def run_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout.strip(), result.stderr.strip()
    except:
        return 'Command failed or timed out', ''

report = {
    'timestamp': datetime.now().isoformat(),
    'system': {
        'platform': platform.platform(),
        'architecture': platform.architecture(),
        'processor': platform.processor(),
        'python_version': sys.version,
        'hostname': platform.node()
    },
    'environment': dict(os.environ),
    'processes': run_command('ps aux | head -20')[0],
    'memory': run_command('free -h')[0],
    'disk': run_command('df -h')[0],
    'network': run_command('netstat -tuln')[0],
    'services': run_command('systemctl list-units --type=service --state=running | head -20')[0]
}

with open('system_report.json', 'w') as f:
    json.dump(report, f, indent=2, default=str)

print('系统报告已生成: system_report.json')
"
```

### 5. 恢复出厂设置

```bash
# 备份当前配置
cp .env .env.backup
cp -r logs logs.backup

# 重置为默认配置
python scripts/environment_manager.py --force
cp .env.example .env

# 重新配置
python qbittorrent_monitor/config_validator.py --fix
```

---

## 📞 获取帮助

### 收集诊断信息

```bash
# 创建诊断包
mkdir -p diagnostics
cp .env diagnostics/
cp logs/*.log diagnostics/ 2>/dev/null || true
python scripts/environment_manager.py --info > diagnostics/environment_info.txt
python qbittorrent_monitor/config_validator.py > diagnostics/config_validation.txt
ps aux > diagnostics/processes.txt
netstat -tuln > diagnostics/network.txt

# 打包诊断信息
tar -czf qbittorrent-monitor-diagnostics-$(date +%Y%m%d).tar.gz diagnostics/

echo "诊断包已创建: qbittorrent-monitor-diagnostics-$(date +%Y%m%d).tar.gz"
```

### 提交问题报告

在提交问题时，请包含：

1. **系统信息**: 操作系统、Python版本、硬件配置
2. **错误信息**: 完整的错误堆栈
3. **配置信息**: `.env`文件（隐藏敏感信息）
4. **日志信息**: 相关的错误日志
5. **复现步骤**: 如何重现问题
6. **诊断包**: 运行诊断脚本生成的信息

### 联系方式

- **GitHub Issues**: [提交问题](https://github.com/ashllll/qbittorrent-clipboard-monitor/issues)
- **邮箱**: support@example.com
- **文档**: [项目Wiki](https://github.com/ashllll/qbittorrent-clipboard-monitor/wiki)

---

*📝 本文档持续更新，如有新的解决方案请提交PR*