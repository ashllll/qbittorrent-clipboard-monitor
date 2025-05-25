# QBittorrent智能下载助手 - 启动指南

## 🐛 重要修复：种子文件名保持原始名称

### 问题描述
之前添加到qBittorrent的种子文件名都变成了"SexArt"，这是因为程序没有正确处理种子的原始名称。

### ✅ 修复内容
1. **修复了种子重命名问题**：在 `qbittorrent_client.py` 中添加了 `rename` 参数
2. **保持原始文件名**：确保添加种子时使用磁力链接中的原始种子名称
3. **添加日志提示**：显示"保持原始名称"的提示信息

### 🔧 修复位置
文件：`qbittorrent_monitor/qbittorrent_client.py`
```python
# 保留原始种子名称 - 关键修复！
if torrent_name and 'rename' not in kwargs:
    # 确保种子名称不被修改，保持原始名称
    data['rename'] = torrent_name
    self.logger.info(f"保持原始名称: {torrent_name}")
```

## 🚀 快速启动方式

### Windows用户 (推荐PowerShell)
```powershell
# 方式1: PowerShell脚本 (推荐)
.\start_monitor.ps1

# 方式2: 批处理文件
.\start_monitor.bat
```

### Linux/macOS用户
```bash
./start_monitor.sh
```

## 📋 启动脚本功能

### ✨ 自动环境管理
- ✅ **自动检查Python版本**（需要Python 3.8+）
- ✅ **自动创建虚拟环境**（首次运行）
- ✅ **自动激活虚拟环境**
- ✅ **自动升级pip**
- ✅ **自动安装依赖包**（从requirements.txt）
- ✅ **自动检查配置文件**

### 🔍 智能依赖检查
脚本会自动安装以下依赖包：
- `aiohttp==3.11.18` - 异步HTTP客户端
- `pyperclip==1.9.0` - 剪贴板操作
- `watchdog>=3.0.0` - 文件监控 (新增)
- `tenacity>=8.0.0` - 重试机制 (新增)
- `retrying>=1.3.0` - 重试装饰器 (新增)
- `crawl4ai>=0.6.3` - 网页爬虫
- `openai==1.76.0` - AI分类支持
- 其他必要依赖...

## 🛠️ 手动安装步骤

如果自动脚本失败，可以手动执行以下步骤：

### 1. 创建虚拟环境
```bash
python -m venv venv
```

### 2. 激活虚拟环境
```bash
# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 运行程序
```bash
python start.py
```

## 📁 项目结构

```
qbittorrent-clipboard-monitor/
├── start.py                    # 主启动文件
├── start_monitor.ps1           # PowerShell启动脚本 (新增)
├── start_monitor.bat           # Windows批处理启动脚本
├── start_monitor.sh            # Linux/macOS启动脚本
├── requirements.txt            # Python依赖列表 (已更新)
├── qbittorrent_monitor/        # 主程序模块
│   ├── config.json            # 配置文件
│   ├── qbittorrent_client.py  # qBittorrent客户端 (已修复)
│   └── ...                    # 其他模块
└── venv/                      # 虚拟环境 (自动创建)
```

## ⚙️ 配置说明

### qBittorrent设置
确保qBittorrent的Web UI已启用：
1. 打开qBittorrent
2. 工具 → 选项 → Web UI
3. 启用Web用户界面
4. 设置端口（默认8080）
5. 设置用户名和密码

### 配置文件
编辑 `qbittorrent_monitor/config.json`：
```json
{
  "qbittorrent": {
    "host": "192.168.1.28",
    "port": 8989,
    "username": "admin",
    "password": "your_password"
  }
}
```

## 🎯 使用方法

1. **启动程序**：运行启动脚本
2. **复制磁力链接**：程序会自动检测并添加到qBittorrent
3. **复制网页URL**：支持XXXClub等网站的批量下载
4. **AI智能分类**：自动分类到不同目录
5. **安全退出**：使用 Ctrl+C

## 🔧 故障排除

### 常见问题

1. **Python未找到**
   - 安装Python 3.8+
   - 确保Python在PATH中

2. **依赖安装失败**
   - 检查网络连接
   - 尝试使用国内镜像：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt`

3. **qBittorrent连接失败**
   - 检查qBittorrent是否运行
   - 检查Web UI是否启用
   - 检查防火墙设置

4. **文件名变成SexArt**
   - ✅ 已修复！更新后的程序会保持原始文件名

### 日志文件
查看 `magnet_monitor.log` 获取详细的运行日志。

## 🆕 更新日志

### v2.1.0 (最新)
- ✅ **修复文件名问题**：种子保持原始名称
- ✅ **新增PowerShell启动脚本**：更好的Windows支持
- ✅ **完善依赖管理**：自动安装缺失的包
- ✅ **改进错误处理**：更详细的错误信息
- ✅ **优化虚拟环境**：自动创建和管理

### 主要改进
1. 种子添加时保持原始文件名
2. 完善的启动脚本支持
3. 自动依赖检查和安装
4. 更好的错误提示和日志

## 💡 技术支持

如果遇到问题，请检查：
1. 日志文件：`magnet_monitor.log`
2. 配置文件：`qbittorrent_monitor/config.json`
3. qBittorrent Web UI是否可以访问

---
**祝你使用愉快！🎉** 