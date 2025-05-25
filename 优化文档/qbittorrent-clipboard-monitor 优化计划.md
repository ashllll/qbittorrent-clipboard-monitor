# 项目改进方案报告：qbittorrent-clipboard-monitor 优化计划

## 1. 引言

'qbittorrent-clipboard-monitor' 是一个旨在自动化管理磁力链接的项目。其核心功能在于持续监控系统剪贴板，自动捕获磁力链接，并利用智能分类逻辑（结合AI和规则引擎）识别种子内容类型，最终将种子自动添加到配置好的 qBittorrent 客户端中指定的下载路径和分类下。项目通过配置文件 (`config.json`) 实现与 qBittorrent 连接、AI 服务、分类规则及下载路径的灵活管理。

本次项目分析与优化的目标是：基于已完成的项目分析、模块优化建议和AI提示词优化工作，整合所有成果，形成一份全面、结构清晰、内容详实且具有高度可操作性的项目改进方案报告。该报告将作为指导项目未来优化工作的最终交付成果，旨在提升项目的稳定性、准确性、用户体验和可维护性。

## 2. 项目现状综合分析总结

根据任务AajD6的项目分析报告，'qbittorrent-clipboard-monitor' 项目当前采用模块化的异步编程结构，主要由 `ConfigManager` (配置管理)、`QBittorrentClient` (qBittorrent交互)、`AIClassifier` (AI/规则分类)、`ClipboardMonitor` (剪贴板监控) 等核心组件构成。

关键发现总结：

*   项目结构: 项目逻辑清晰，主要功能由独立的类负责，采用 `asyncio` 实现异步操作，并通过 Pydantic 进行配置加载和验证。模块间交互如下图所示：
    ```svg
    <svg width="800" height="650" xmlns="http://www.w3.org/2000/svg">
      <style>
        .class-box { fill: #e0e0e0; stroke: black; stroke-width: 1; }
        .function-box { fill: #c0c0c0; stroke: black; stroke-width: 1; }
        .arrow { marker-end: url(#arrowhead); stroke: black; stroke-width: 1; fill: none; }
        .text { font-family: sans-serif; font-size: 12px; text-anchor: middle; }
        .small-text { font-family: sans-serif; font-size: 10px; }
        .section-title { font-family: sans-serif; font-size: 14px; font-weight: bold; }
      </style>
      <defs>
        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="0" refY="3.5" orient="auto">
          <polygon points="0 0, 10 3.5, 0 7"></polygon>
        </marker>
      </defs>

      <!-- Classes -->
      <rect x="50" y="50" width="150" height="40" rx="5" ry="5" class="class-box"></rect>
      <text x="125" y="75" class="text">AppConfig</text>

      <rect x="250" y="50" width="150" height="40" rx="5" ry="5" class="class-box"></rect>
      <text x="325" y="75" class="text">ConfigManager</text>

      <rect x="450" y="50" width="150" height="40" rx="5" ry="5" class="class-box"></rect>
      <text x="525" y="75" class="text">QBittorrentDiscovery</text>

      <rect x="50" y="150" width="150" height="40" rx="5" ry="5" class="class-box"></rect>
      <text x="125" y="175" class="text">QBittorrentClient</text>

      <rect x="250" y="150" width="150" height="40" rx="5" ry="5" class="class-box"></rect>
      <text x="325" y="175" class="text">AIClassifier</text>

      <rect x="450" y="150" width="150" height="40" rx="5" ry="5" class="class-box"></rect>
      <text x="525" y="175" class="text">ClipboardMonitor</text>

        <rect x="250" y="250" width="150" height="40" rx="5" ry="5" class="class-box"></rect>
      <text x="325" y="275" class="text">DeepSeekConfig</text>

      <rect x="50" y="250" width="150" height="40" rx="5" ry="5" class="class-box"></rect>
      <text x="125" y="275" class="text">QBittorrentConfig</text>

       <rect x="450" y="250" width="150" height="40" rx="5" ry="5" class="class-box"></rect>
      <text x="525" y="275" class="text">CategoryConfig</text>


      <!-- Main Function -->
      <rect x="300" y="350" width="150" height="40" rx="5" ry="5" class="function-box"></rect>
      <text x="375" y="375" class="text">main()</text>

        <!-- Other Functions -->
      <rect x="50" y="350" width="150" height="40" rx="5" ry="5" class="function-box"></rect>
      <text x="125" y="375" class="text">setup_logging()</text>

      <rect x="600" y="350" width="150" height="40" rx="5" ry="5" class="function-box"></rect>
      <text x="675" y="375" class="text">parse_magnet()</text>


      <!-- Relationships -->

      <!-- ConfigManager loads config -->
      <path d="M325 90 V 120 H 125" class="arrow"></path>
      <text x="225" y="110" class="small-text">Loads/Uses</text>
        <path d="M325 90 V 120 H 325 V 145" class="arrow"></path>
       <path d="M325 90 V 120 H 525" class="arrow"></path>
      <text x="425" y="110" class="small-text">Loads/Uses</text>
       <path d="M325 90 V 245 H 325" class="arrow"></path>
         <path d="M325 90 V 245 H 125" class="arrow"></path>
         <path d="M325 90 V 245 H 525" class="arrow"></path>


      <!-- ConfigManager uses Discovery -->
      <path d="M450 70 H 410 V 70 H 200" class="arrow"></path>
      <text x="325" y="60" class="small-text">Uses</text>
      <path d="M450 70 H 410 V 70 H 200"></path> <!-- No marker for this direction -->

      <!-- ClipboardMonitor uses AIClassifier -->
      <path d="M450 170 H 410 V 170 H 200" class="arrow"></path>
      <text x="325" y="160" class="small-text">Uses</text>
      <path d="M450 170 H 410 V 170 H 200"></path>

      <!-- ClipboardMonitor uses QBittorrentClient -->
      <path d="M450 170 H 410 V 170 H 200" class="arrow"></path>
      <text x="325" y="160" class="small-text">Uses</text>
       <path d="M450 170 H 410 V 170 H 200"></path>


      <!-- AIClassifier uses DeepSeekConfig -->
       <path d="M325 250 V 200" class="arrow"></path>
       <text x="350" y="225" class="small-text">Uses</text>

       <!-- QBittorrentClient uses QBittorrentConfig -->
       <path d="M125 250 V 200" class="arrow"></path>
       <text x="150" y="225" class="small-text">Uses</text>

       <!-- AIClassifier uses CategoryConfig (via classify method param) -->
       <path d="M450 270 H 420 V 220 H 400" class="arrow"></path>
       <text x="425" y="240" class="small-text">Uses (via param)</text>

      <!-- main uses components -->
      <path d="M375 350 V 300 V 190" class="arrow"></path>
        <path d="M375 350 V 300 H 150 V 190" class="arrow"></path>
       <path d="M375 350 V 300 H 550 V 190" class="arrow"></path>
       <path d="M375 350 V 300 H 150 V 90" class="arrow"></path>
       <path d="M375 350 V 300 H 350 V 90" class="arrow"></path>
       <path d="M375 350 V 300 H 550 V 90" class="arrow"></path>
       <text x="400" y="325" class="small-text">Initializes/Uses</text>

        <!-- main uses setup_logging -->
       <path d="M300 370 H 200" class="arrow"></path>
       <text x="250" y="380" class="small-text">Uses</text>

        <!-- parse_magnet used by QBittorrentClient and ClipboardMonitor -->
        <path d="M600 370 H 580 V 190 H 550" class="arrow"></path>
        <text x="570" y="280" class="small-text">Uses</text>
         <path d="M600 370 H 580 V 190 H 150" class="arrow"></path>

    </svg>
*   主要功能: 实现了剪贴板磁力链接的监控、解析、AI/规则分类以及通过 Web UI 添加到 qBittorrent 并指定分类和路径。具备基础的 qBittorrent API 交互能力和网络重试。
*   现有AI提示词: 当前 AI 分类主要依赖 DeepSeek AI 的 `deepseek-chat` 模型，通过 `openai` 库调用。提示词包含种子名称、可用分类描述和基于名称的简单规则。
*   初步识别的改进点: 报告AajD6初步识别了AI分类健壮性不足、规则引擎简单、缺乏用户交互界面、配置管理灵活性有限、测试覆盖缺失、依赖管理方式传统、容器化支持待完善以及未能充分利用种子元数据等多个改进方向。

## 3. 详细功能模块优化改进建议

本节整合任务Admq9的成果，系统性地阐述针对各功能模块的优化改进建议。

### 3.1. 配置管理 (Configuration Management)

*   当前状况: 配置主要依赖单一 `config.json` 文件，Pydantic 加载验证，支持环境变量覆盖。
*   建议的改进措施: 引入更灵活的配置库，支持多格式 (YAML, TOML) 和层级结构，实现配置热加载。
*   具体实现思路:
    *   使用 `Dynaconf` 等库替代现有配置加载逻辑，支持多种文件格式。
    *   利用 `Dynaconf` 的热加载功能或 `watchdog` 库监控配置文件变化，并在文件更新时重新加载配置，更新相关运行时对象。需处理好线程安全。
*   预期效果: 增强配置灵活性和运维便利性，无需重启即可应用部分配置更改。

### 3.2. qBittorrent客户端交互 (qBittorrent Client Interaction)

*   当前状况: 使用 `aiohttp` 实现异步通信，包含登录、分类、添加、重复检查。未充分利用全部 API。
*   建议的改进措施: 增强 API 调用，增加种子列表获取（优化重复检查）、管理操作（暂停/恢复/删除），优化错误处理和重试逻辑。
*   具体实现思路:
    *   查阅 qBittorrent Web API 文档，在 `QBittorrentClient` 中增加更多方法 (`/api/v2/torrents/info`, `/api/v2/torrents/delete` 等)。
    *   使用 `tenacity` 等库为 API 调用实现基于 HTTP 状态码和错误类型的智能指数退避重试。
*   预期效果: 增强项目功能，为高级管理操作打下基础；提高网络不稳定时的操作成功率。

### 3.3. AI分类逻辑 (AI Classification Logic)

*   当前状况: 使用 DeepSeek AI 通过 `openai` 库进行分类，AI 调用包裹在 `asyncio.to_thread` 中，缺乏健壮的重试机制。
*   建议的改进措施: 增强 AI API 调用的健壮性（重试、超时），优化提示词工程，支持 Few-shot 示例。
*   具体实现思路:
    *   在 `AIClassifier.classify` 中增加 `try...except` 捕获 OpenAI 异常，使用 `tenacity` 实现针对 `RateLimitError` 等的指数退避重试。
    *   为 API 调用设置超时参数。
    *   修改 `AppConfig` 和 `DeepSeekConfig` 支持 Few-shot 示例配置，修改 `_build_prompt` 方法将 Few-shot 示例和超时配置集成到提示词中。
*   预期效果: 提高 AI 分类成功率和稳定性，避免长时间阻塞；优化的提示词（特别是 Few-shot）能提高分类准确性。

### 3.4. 规则引擎分类 (Rule Engine Classification)

*   当前状况: 基于简单的关键词匹配，规则逻辑硬编码。
*   建议的改进措施: 增强规则引擎能力，支持正则表达式、排除关键词、优先级等，将规则外部化配置。
*   具体实现思路:
    *   修改 `CategoryConfig` 或新增配置结构，允许为每个分类定义包含类型 (`keyword`, `regex`, `exclude`), 内容和优先级的规则列表。
    *   重写 `AIClassifier._rule_based_classify` 方法，解析并应用新的规则结构，实现复杂的匹配逻辑和优先级判断。
*   预期效果: 提高规则分类的灵活性和可定制性，增强 AI 退回机制的准确性。

### 3.5. 错误处理机制 (Error Handling Mechanism)

*   当前状况: 定义了特定异常类，部分操作有基础重试，AI 错误处理简单，主循环捕获有限。
*   建议的改进措施: 建立统一的错误处理策略，细化异常类型，在所有外部交互点实现健壮捕获和处理（重试、回退、日志），集成通知系统。
*   具体实现思路:
    *   定义更具体的异常类（`QbtAuthError`, `AIApiError` 等）。
    *   在各模块关键方法中增加细致 `try...except` 块，根据异常类型执行不同策略。
    *   集成 `Apprise` 等通知库，在捕获到关键错误时发送通知。通知配置添加到 `config.json`。
*   预期效果: 提高程序稳定性和弹性，更好地诊断问题，用户能及时感知程序状态。

### 3.6. 用户交互与监控界面 (User Interaction & Monitoring Interface)

*   当前状况: 主要通过控制台日志提供信息，无图形/Web 界面，无内置通知。
*   建议的改进措施: 开发简单的 Web UI 或 CLI 扩展，提供状态查看、日志、历史记录、配置修改功能；集成多种通知渠道。
*   具体实现思路:
    *   Web UI: 使用 FastAPI/Flask 框架，暴露内部状态和操作接口，开发简单前端页面。
    *   CLI: 使用 `Click` 库增加子命令。
    *   通知: 使用 `Apprise` 集成 Telegram, Discord 等通知渠道，在关键事件触发。
*   预期效果: 提升用户友好性和易用性，用户无需命令行即可监控和管理，及时了解重要事件。

### 3.7. 元数据利用增强 (Metadata Utilization Enhancement)

*   当前状况: 主要基于种子名称分类，未利用种子文件中的文件列表、大小等元数据。
*   建议的改进措施: 在添加种子后获取元数据，将其作为辅助信息用于分类判断。
*   具体实现思路:
    *   修改 `QBittorrentClient`，增加调用 qBittorrent API 获取种子文件列表 (`/api/v2/torrents/propertiesFiles`) 和 info (`/api/v2/torrents/info`) 的方法。
    *   在 `ClipboardMonitor._process_magnet` 中调用新方法获取元数据。
    *   修改 `AIClassifier.classify` 和 `_rule_based_classify` 接受元数据参数，并在构建提示词或规则匹配时利用这些信息。
*   预期效果: 显著提高分类准确性，特别是区分命名模糊或相似内容（如电影 vs 剧集合集）；为未来功能扩展（如基于文件类型过滤）打下基础。

### 3.8. 测试策略 (Testing Strategy)

*   当前状况: 分析报告未提及测试覆盖或策略。
*   建议的改进措施: 建立单元、集成、端到端测试策略，编写测试用例，集成 CI/CD。
*   具体实现思路:
    *   使用 `pytest` 和 `pytest-asyncio` 测试框架。
    *   编写单元测试，使用 Mock 模拟外部依赖。
    *   编写集成测试，测试模块间交互。
    *   在 CI/CD (如 GitHub Actions) 中配置自动化测试流程。
*   预期效果: 提高代码质量和可靠性，简化重构，自动化发现 Bug。

### 3.9. 依赖项管理方式 (Dependency Management Method)

*   当前状况: `requirements.txt` 管理依赖，未锁定整个依赖树版本。
*   建议的改进措施: 采用现代工具 (`Poetry`/`Pipenv`) 管理依赖，锁定完整依赖树，集成虚拟环境管理。
*   具体实现思路:
    *   选择 `Poetry` 或 `Pipenv`。
    *   通过工具迁移现有依赖到 `pyproject.toml`，生成 `poetry.lock`/`Pipfile.lock`。
    *   更新文档和 CI/CD 使用新工具安装依赖。
*   预期效果: 确保环境构建一致性，简化依赖管理，更好解决版本冲突。

### 3.10. 容器化部署方案 (Containerized Deployment Solution)

*   当前状况: 项目考虑了路径映射，但未提供官方 Dockerfile/Docker Compose。
*   建议的改进措施: 提供官方 Dockerfile 和 Docker Compose 配置。
*   具体实现思路:
    *   创建 Dockerfile，基于 Python 基础镜像，安装依赖，复制代码，设置入口点。确保日志输出到 stdout/stderr。
    *   创建 Docker Compose 文件，定义服务，配置卷（挂载配置、日志），环境变量，网络。
*   预期效果: 大幅提升部署便捷性、环境隔离和可移植性。

### 3.11. AI模型扩展性 (AI Model Extensibility)

*   当前状况: AI 分类器硬编码使用 DeepSeek API 和 `openai` 库。
*   建议的改进措施: 抽象 AI 分类器接口，通过配置支持不同 AI 服务商/模型 (OpenAI, Claude, Gemini)。
*   具体实现思路:
    *   定义 `BaseAIClassifier` 抽象基类，包含 `classify` 方法。
    *   创建 `DeepSeekClassifier`, `OpenAIClassifier` 等具体实现类。
    *   在初始化时，根据配置动态创建对应的实现类实例 (工厂模式)。
    *   修改配置模型支持不同 AI 服务商配置。
*   预期效果: 提供 AI 模型选择灵活性，便于用户根据成本、性能选择；增强项目可扩展性。

### 3.12. 路径映射灵活性 (Path Mapping Flexibility)

*   当前状况: 支持单个全局映射规则，逻辑简单。
*   建议的改进措施: 支持多个映射规则，允许为不同分类指定不同映射规则，支持更复杂匹配。
*   具体实现思路:
    *   修改 `AppConfig` 将 `path_mapping` 改为列表。
    *   在 `CategoryConfig` 增加可选 `path_mapping` 字段。
    *   修改 `QBittorrentClient._map_save_path` 实现规则列表遍历，分类规则优先。
*   预期效果: 适应复杂部署环境和个性化下载目录需求，配置更清晰。

## 4. AI提示词优化方案

本节整合任务dMjEo的成果，详细呈现优化后的AI提示词、优化理由、具体修改内容及预期效果。

### 4.1. 优化后的AI提示词

System Message (系统消息):

```text
你是一个专业的种子分类助手。你的任务是根据用户提供的种子信息，严格遵循给定的分类规则和可用分类列表，将其分类到最合适的类别中。必须且只能返回一个分类名称，不要包含任何其他文字、解释、标点或符号。如果无法确定，请返回 'other'。
```

Optimized User Prompt Template (优化后的用户提示词模板):

```python
"""请根据以下信息，将种子分类到最合适的类别中。

---
任务目标: 根据种子信息，从提供的列表中选择一个最匹配的分类。

---
可用分类列表及其详细描述:
{category_descriptions_with_keywords}

---
待分类种子信息:
种子名称: {torrent_name}
种子哈希: {torrent_hash}
文件列表: {file_list}
总大小: {total_size}

---
分类规则与考量 (AI应优先参考这里的规则和可用分类列表):
1.  核心判断: 主要依据“种子名称”、“文件列表”和“总大小”判断内容类型。
2.  特征识别:
    *   电视剧: 通常包含SXXEXX格式的季/集信息，或"Season"、"Episode"、"剧集"等词。文件列表中可能包含多个视频文件。
    *   电影: 通常包含年份(如2020)、分辨率(1080p, 4K, 2160p)、编码(H.264, HEVC)、来源标签(BluRay, WEB-DL, BDRip)。文件列表中通常包含单个或少数视频文件。
    *   成人内容: 通常包含明显的成人关键词、成人制作商名称、或特定的文件命名模式。
    *   日本动画 (Anime): 通常包含"动画"、"动漫"、"[机构/字幕组]"、"UNCENSORED"、"无修"等术语。
    *   音乐 (Music): 通常包含专辑/艺术家名称、格式(FLAC, MP3)、"Album"等词。文件列表中通常包含音频文件和封面图片。
    *   游戏 (Games): 通常包含游戏名称、平台(PC, Switch)、"Reloaded", "CODEX"等破解组名称。文件列表中可能包含安装文件、可执行文件。
    *   软件 (Software): 通常包含软件名称、版本号、操作系统(Windows, macOS)。文件列表中可能包含安装包、注册机。
3.  优先级: 如果种子信息同时符合多个分类的描述和规则，选择最具体的或最符合核心内容的分类。
4.  不确定处理: 如果种子信息非常模糊，或不明显属于任何明确分类，返回 'other'。
5.  输出格式: 严格遵循系统消息的输出要求，只返回分类名称，例如：`movies` 或 `tv`。

---
少量示例 (Few-Shot Examples) - 供参考和学习输出格式:
Input:
种子名称: [SubsPlease] Dungeon Meshi - 14 (1080p) [F65594EE].mkv
文件列表: ["Dungeon Meshi - 14.mkv"]
总大小: 350MB
Output: anime

Input:
种子名称: The.Lord.of.the.Rings.The.Fellowship.of.the.Ring.2001.EXTENDED.UHD.BluRay.2160p.TrueHD.Atmos.7.1.HEVC.REMUX-FraMeSToR
文件列表: ["The Lord of the Rings The Fellowship of the Ring 2001 EXTENDED UHD BluRay 2160p TrueHD Atmos 7.1 HEVC REMUX-FraMeSToR.mkv"]
总大小: 98GB
Output: movies

Input:
种子名称: Succession S04E09 1080p WEB-DL DD+5.1 H.264-NTb
文件列表: ["Succession.S04E09.1080p.WEB-DL.DD+5.1.H.264-NTb.mkv"]
总大小: 2GB
Output: tv

Input:
种子名称: 1577505565
文件列表: []
总大小: 0MB
Output: other

Input:
种子名称: VA - Billboard Hot 100 [2024-07-20] [WEB] [24bit] [FLAC]
文件列表: ["01. Artist Name - Song Title.flac", "02. Artist Name - Song Title.flac", "cover.jpg"]
总大小: 1.5GB
Output: music

Input:
种子名称: Adobe Photoshop 2024 v25.9.1 RePack by KpoJIuK
文件列表: ["Setup.exe", "Crack.dll", "Instructions.txt"]
总大小: 4GB
Output: software

Input:
种子名称: Elden Ring
文件列表: ["eldenring.exe", "steam_api64.dll", "..."]
总大小: 50GB
Output: games

Input:
种子名称: User provided category not in list or is ambiguous
文件列表: []
总大小: 0MB
Output: other

---
请根据以上信息，判断最合适的分类，并只输出分类名称。
"""
```
*(注: `{category_descriptions_with_keywords}`, `{torrent_hash}`, `{file_list}`, `{total_size}` 为需要由代码动态填充的新占位符。)*

### 4.2. 优化理由详细解释

1.  引入 Few-shot Examples (少量示例): 通过具体示例直观教授模型输入格式、期望输出格式及判断逻辑，是提高 LLM 在特定任务上准确性和遵循指令能力的最有效方法之一。
2.  集成更多元数据 (文件列表, 总大小): 种子名称可能模糊或误导，文件列表和总大小提供了种子内容的客观信息。利用这些信息能显著提高分类准确性，尤其在名称不清晰时，有助于区分文件名相似但内容不同的种子（如电影 vs 剧集合集，软件 vs 游戏）。
3.  强化系统消息和输出格式约束: 将严格输出格式要求放在系统消息中并结合 Few-shot 示例演示，最大限度减少模型“健谈”或输出格式错误的可能，确保输出可直接解析。
4.  优化提示词结构和分类规则描述: 清晰的结构和更详细、结合多源信息的规则描述，有助于 AI 理解不同组成部分的作用，指导其更合理地综合信息进行判断。

### 4.3. 具体修改内容

*   System Message 修改: 增加了“严格遵循规则和列表”要求，并加强了输出格式约束（“必须且只能”），明确不确定时返回 'other'。
*   User Prompt Template 修改:
    *   引入 `---` 分隔符，结构化为任务目标、可用分类、待分类信息、规则与考量、少量示例、最终指令等逻辑块。
    *   新增“任务目标”块。
    *   合并并优化“可用分类”和“关键词提示”为新的 `{category_descriptions_with_keywords}` 占位符。
    *   在“待分类种子信息”块新增 `{torrent_hash}`, `{file_list}`, `{total_size}` 占位符。
    *   “分类规则与考量”规则更详细，强调结合多源信息，新增优先级规则。
    *   新增“少量示例 (Few-Shot Examples)”块，包含多组 Input/Output 示例对。
    *   调整最终指令。

### 4.4. 优化后提示词的预期效果和具体好处

*   提高分类准确性: Few-shot 示例、更多元数据以及优化的规则描述共同作用，使 AI 判断更基于实际内容，显著减少误分类。
*   提高分类一致性: Few-shot 示例和强化输出约束引导 AI 在相似输入下给出一致结果，降低随机性。
*   更好地处理边缘案例: 示例和详细规则提高了 AI 处理名称模糊、多重含义或不常见命名模式的能力。不确定时返回 'other' 提供可靠回退。
*   减少模型幻觉: 结构清晰、任务明确、更多客观证据（元数据）约束了 AI 的判断，使其更聚焦于任务。
*   提升整体AI分类模块鲁棒性: AI 分类本身更可靠，配合后端 API 调用健壮性改进，整体流程更稳定。

实现优化后提示词所需的技术支持和代码调整建议:

1.  修改 `AIClassifier._build_prompt` 方法:
    *   适配新的提示词模板结构。
    *   需要逻辑来生成 `{category_descriptions_with_keywords}` 的内容，结合 `category_descriptions` 和 `category_keywords` 配置。
    *   填充所有新的占位符 (`{torrent_name}`, `{torrent_hash}`, `{file_list}`, `{total_size}`)。
2.  实现获取元数据的逻辑:
    *   参照模块优化建议 (3.7)，修改 `QBittorrentClient` 增加获取文件列表和总大小的 API 调用方法。
    *   修改 `ClipboardMonitor._process_magnet`，在添加种子后调用 qBittorrent API 获取这些元数据。
    *   将获取到的元数据作为参数传递给 `AIClassifier.classify` 方法。如果无法获取（如 qBittorrent 暂时无响应），应传入空列表和默认大小（如 0MB）。
3.  修改配置模型:
    *   修改 `AppConfig` 和 `DeepSeekConfig` Pydantic 模型，支持 Few-shot 示例列表配置。
4.  修改 `AIClassifier` 初始化和调用:
    *   读取配置中的 Few-shot 示例。
    *   调整 `classify` 方法，使其能够接受文件列表和总大小等参数。

## 5. 综合实施路线图

基于上述分析和建议，提出一个高层次的实施优化路线图：

阶段 1: 核心稳定性与可靠性增强 (优先级：高)

*   目标: 显著提升程序在处理错误、外部服务不稳定时的鲁棒性，减少崩溃和误操作。
*   关键改进:
    *   实现 AI API 调用的健壮重试和超时机制 (3.3)。
    *   优化 qBittorrent 客户端交互的错误处理和智能重试 (3.2)。
    *   建立统一的错误处理策略，细化异常并增强捕获 (3.5)。
    *   采用现代依赖管理工具 (`Poetry`/`Pipenv`)，锁定依赖版本 (3.9)。
    *   为核心模块 (ConfigManager, QBittorrentClient, AIClassifier 的独立逻辑) 编写单元测试 (3.8)。
*   预期成果: 程序运行更稳定，更能应对网络波动和 API 服务临时问题，依赖管理更规范。

阶段 2: 分类准确性与功能增强 (优先级：中高)

*   目标: 利用更多信息提升种子分类的准确性，增强规则引擎能力。
*   关键改进:
    *   实现获取种子元数据 (文件列表, 总大小) 的逻辑 (3.7)。
    *   实施优化后的 AI 提示词 (4.)，在调用 AI 时传递元数据和 Few-shot 示例。
    *   增强规则引擎能力，外部化规则配置，使其支持更复杂的匹配 (3.4)。
    *   优化路径映射逻辑，支持多规则和分类特定映射 (3.12)。
*   预期成果: AI 分类准确性显著提高，规则引擎更强大灵活，下载路径设置更精准。

阶段 3: 用户体验与部署优化 (优先级：中)

*   目标: 提升项目的易用性，简化部署，增强用户对程序运行状态的感知。
*   关键改进:
    *   实现配置热加载功能 (3.1)。
    *   集成通知系统 (3.5, 3.6)。
    *   提供官方 Dockerfile 和 Docker Compose 配置 (3.10)。
    *   开发简易 Web UI 或 CLI 扩展用于状态监控和基本操作 (3.6)。
    *   研究 AI 模型扩展性，抽象接口 (3.11)。
    *   扩展集成测试和端到端测试 (3.8)。
*   预期成果: 用户管理和监控程序更方便，部署更快捷，未来可扩展性增强。

优先级考量: 稳定性是基础，应优先解决。分类准确性是项目核心价值，紧随其后。用户体验和部署优化可以作为中后期改进。测试策略和依赖管理贯穿始终，应尽早启动。

## 6. 结论

通过实施本报告提出的综合改进方案，'qbittorrent-clipboard-monitor' 项目将在多个维度获得显著提升。核心的改进点包括增强 AI 分类逻辑的健壮性和准确性（通过优化提示词、整合元数据和 Few-shot 示例），提升规则引擎的灵活性，构建更全面和智能的错误处理及通知机制，优化与 qBittorrent 的交互，以及改进配置管理、依赖管理、测试策略、用户界面和容器化部署等方面。

这些优化将使项目更加稳定、可靠、易用且可维护。最终，用户将体验到更准确、更顺畅的磁力链接自动化分类和下载流程，显著提升使用效率和便利性。本报告将作为项目优化的行动蓝图，指导后续的开发工作。