# 日志高亮工具

这是一个用于高亮日志文件中特定关键字的工具，旨在帮助用户快速识别日志中的重要信息。

## 功能

- 扫描日志文件并高亮指定的关键字。
- 支持多种文件格式和压缩文件的处理。
- 提供详细的扫描结果和统计信息。

## 安装

```bash
# 克隆仓库
git clone https://github.com/ashllll/log_hightlight.git
cd log_hightlight

# 安装依赖
pip install -r requirements.txt
```

## 使用方法

```bash
# 运行工具
python main.py --input <日志文件路径> --keywords <关键字列表>
```

## 参数说明

- `--input`：指定要扫描的日志文件或目录路径。
- `--keywords`：指定要高亮的关键词列表，用逗号分隔。

## 示例

```bash
python main.py --input ./logs --keywords error,exception
```

## 代码架构与流程图

详细的代码架构和流程图请参见 [architecture_and_flowchart.md](architecture_and_flowchart.md) 文件。

## 贡献

欢迎提交问题和拉取请求。对于重大更改，请先开一个 issue 讨论您想要更改的内容。

## 许可证

本项目采用 MIT 许可证 - 详情请见 [LICENSE.md](LICENSE.md) 文件。
