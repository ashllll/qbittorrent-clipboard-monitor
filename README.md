# qBittorrent 剪贴板监控与自动分类下载器

这是一个Python脚本，用于监控系统剪贴板中的磁力链接，并使用DeepSeek AI（或规则引擎备用）自动对种子进行分类，然后将种子添加到qBittorrent客户端的相应分类下。

## 功能

*   **剪贴板监控**: 持续监控剪贴板，自动检测磁力链接。
*   **自动分类**: 
    *   优先使用DeepSeek AI分析种子名称进行智能分类。
    *   当AI不可用或分类失败时，自动切换到基于关键词和模式的规则引擎进行分类。
*   **qBittorrent集成**: 自动将磁力链接添加到qBittorrent，并设置对应的分类和下载路径。
*   **分类管理**: 自动检查并创建qBittorrent中缺失的分类。
*   **配置灵活**: 通过 `config.json` 文件轻松配置qBittorrent连接、DeepSeek API、分类规则和路径映射。
*   **重复检测**: 添加种子前检查是否已存在，避免重复下载。
*   **异步处理**: 使用 `asyncio` 实现高效的异步操作。
*   **错误处理与重试**: 包含网络请求的重试机制。

## 使用流程

1.  **环境准备**:
    *   确保已安装 Python 3。
    *   确保已安装 qBittorrent 并启用 Web UI。

2.  **克隆仓库**:
    ```bash
    git clone https://github.com/ashjoe/qbittorrent-clipboard-monitor.git
    cd qbittorrent-clipboard-monitor
    ```

3.  **创建虚拟环境**:
    ```bash
    python3 -m venv qbit_venv
    source qbit_venv/bin/activate  # Linux/macOS
    # 或者
    # qbit_venv\Scripts\activate  # Windows
    ```

4.  **安装依赖**: 
    ```bash
    pip install -r requirements.txt
    ```
    (如果 `requirements.txt` 不存在，请运行: `pip install aiohttp pyperclip openai pydantic`)

5.  **配置 `config.json`**:
    *   进入 `qbittorrent_monitor` 目录。
    *   复制 `config.json.example` (如果存在) 为 `config.json`，或者直接修改 `config.json`。
    *   **qBittorrent 配置**: 填写正确的 qBittorrent Web UI 地址 (`host`, `port`)、用户名 (`username`) 和密码 (`password`)。
    *   **DeepSeek 配置 (可选但推荐)**:
        *   在 `deepseek` 部分的 `api_key` 字段填入您的 DeepSeek API 密钥。
        *   **强烈建议**: 不要直接将密钥写入 `config.json`，而是将其设置在环境变量 `DEEPSEEK_API_KEY` 中。脚本会优先读取环境变量。
        *   如果留空且未设置环境变量，脚本将使用规则引擎进行分类。
    *   **分类配置**: 根据需要调整 `categories` 部分，定义分类名称、下载路径 (`savePath`)、关键词 (`keywords`) 和描述 (`description`)。
    *   **路径映射 (可选)**: 如果脚本运行环境（如Docker）与qBittorrent的路径不同，配置 `path_mapping` 进行映射。如果可以直接访问NAS路径，设置 `use_nas_paths_directly` 为 `true`。

6.  **运行脚本**:
    *   确保虚拟环境已激活。
    *   在项目根目录下运行：
    ```bash
    python qbittorrent_monitor/qbittorrent_clipboard_with_category_optimized_v0.1.py
    ```

7.  **使用**: 脚本启动后，它将在后台运行并监控剪贴板。复制任何磁力链接，脚本将自动处理并添加到qBittorrent。

## 下一步可能的开发方向

*   **Web UI/API**: 开发一个简单的Web界面或API，用于查看日志、修改配置、手动添加链接等。
*   **更高级的规则引擎**: 增强规则引擎的灵活性，支持更复杂的匹配逻辑（如正则表达式权重、排除规则等）。
*   **多AI模型支持**: 支持切换或集成其他AI模型进行分类（如Claude, Gemini）。
*   **通知系统**: 添加下载完成或添加失败的通知（如通过Telegram, Discord）。
*   **种子元数据提取**: 解析磁力链接或种子文件以获取更详细的信息（如文件列表、大小），用于更精确的分类。
*   **Docker化**: 提供Dockerfile，方便容器化部署。
*   **单元测试与集成测试**: 增加测试用例，提高代码健壮性。
*   **插件化架构**: 将分类器（AI、规则）、通知等模块设计为插件，方便扩展。
*   **更好的依赖管理**: 使用如 `poetry` 或 `pipenv` 进行依赖管理。

## 许可证

本项目使用 MIT 许可证。 