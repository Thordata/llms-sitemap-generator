# LLMS Sitemap Generator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://badge.fury.io/py/llms-sitemap-generator.svg)](https://badge.fury.io/py/llms-sitemap-generator)

**面向 LLM 的 `llms.txt` 与 sitemap 生成器** - 自动收集、过滤和组织网站 URL，生成面向 LLM 和搜索引擎的策展式索引。

为任何网站生成 SEO 友好的 sitemap 和 LLM 优化的 `llms.txt` 文件，从简单博客到复杂 B2B SaaS 平台。支持 sitemap、爬虫或手动 URL 列表。包含可视化 GUI 工具，支持 Windows .exe 构建。

## ✨ 核心特性

**适用于：**
- 🤖 **LLM 训练**：为 AI 模型训练和 RAG 系统生成 `llms.txt` 文件
- 🔍 **SEO 优化**：为搜索引擎索引创建全面的 sitemap
- 📊 **内容发现**：自动发现和编录所有网站页面
- 🌐 **多语言网站**：智能语言过滤，支持国际化网站
- 🏢 **企业网站**：处理具有多个子域的复杂 B2B SaaS 站点

## 🚀 功能特性

- **通用易用**
  - 适用于任何网站：从简单博客到复杂 B2B SaaS 站点
  - 简单配置，智能默认值
  - GUI 图形界面工具（无需编程）
- **URL 来源**：
  - 从 `sitemap.xml` 导入（支持 sitemap index）
  - 无 sitemap 时，从首页或任意入口 URL 爬取
  - 自动从 sitemap 发现子域名
  - 静态 URL 列表用于手动补充
- **过滤与分组**：
  - include / exclude 正则规则
  - 自动按路径首段分组（Home / Products / Docs / Pricing / Blog 等）
  - 语言过滤：`llms.txt` 仅默认语言，`sitemap.xml` 包含所有语言
  - 支持 profile 定义不同输出层级（minimal / recommended / full）
  - 每组限制数量，控制输出规模
- **输出格式**：
  - `llms.txt`：分组的精简 Markdown 索引，符合 oxlabs.io 格式标准
  - `llms-full.txt`：带更多字段的长版（可选）
  - `llms.json`：结构化 JSON（可选）
  - `sitemap.xml` / `sitemap_index.xml`：SEO 友好的 sitemap，包含所有语言（可选）

## 📦 安装

```bash
# 基础安装
pip install llms-sitemap-generator

# 带 GUI 支持（可选）
pip install llms-sitemap-generator[gui]
```

## 🎯 快速开始

```bash
pip install llms-sitemap-generator

llms-sitemap-generator --help
```

### 1. 初始化 / 分析站点

在当前目录生成一个基础配置：

```bash
llms-sitemap-generator init
```

或直接让工具分析站点并生成推荐配置：

```bash
llms-sitemap-generator analyze https://example.com
```

### 2. 生成 `llms.txt`

根据你的网站修改 `llmstxt.config.yml` 后：

```bash
# 先做一次干跑，方便看分组和 URL 选择情况
llms-sitemap-generator generate --dry-run --max-pages 100

# 正式生成 llms.txt（以及配置中的其他输出）
llms-sitemap-generator generate

# 如需更快测试，可跳过抓取页面内容
llms-sitemap-generator generate --no-fetch
```

### 3. 控制输出规模与分组

在配置里通过 `filters.profiles` 定义不同分组层级后，可以用：

```bash
llms-sitemap-generator generate --profile minimal
llms-sitemap-generator generate --profile recommended
llms-sitemap-generator generate --profile full
```

或临时只保留部分分组（优先级高于 profile）：

```bash
llms-sitemap-generator generate --only-groups "Home,Products"
```

## 基本配置示例

```yaml
site:
  base_url: "https://example.com"
  default_language: "en"

sources:
  - type: "sitemap"
    url: "https://example.com/sitemap.xml"

filters:
  include:
    - pattern: "^/products"
      group: "Products"
      priority: 100
    - pattern: "^/docs"
      group: "Docs"
      priority: 90
    - pattern: "^/pricing"
      group: "Pricing"
      priority: 80

  exclude:
    - pattern: "blog"
    - pattern: "news"
    - pattern: "^/careers"

  # 过滤之后的全局 URL 上限，保证 llms.txt 尽量聚焦
  max_urls: 1000
  auto_group: true

output:
  llms_txt: "llms.txt"
  llms_full_txt: "llms-full.txt"
  llms_json: "llms.json"
  sitemap_xml: "sitemap.xml"
  sitemap_index: "sitemap_index.xml"
```

## 常用命令

- `llms-sitemap-generator init`：在当前目录创建示例配置 `llmstxt.config.yml`。
- `llms-sitemap-generator analyze URL`：分析网站结构并生成推荐配置。
- `llms-sitemap-generator generate`：生成 `llms.txt`（以及可选的其他输出）。
- `llms-sitemap-generator gui`：启动可选 GUI（需要安装 `PyQt5`）。

## GUI / Windows EXE（可选）

- **GUI 工具**：在安装 `pip install llms-sitemap-generator[gui]` 后，可运行 `llms-sitemap-generator gui` 启动图形界面。
  - 可视化配置界面
  - 实时 URL 收集和预览
  - 子域名发现和选择
  - 分组选择和过滤
  - 详见 `docs/gui-usage.md`。
- **Windows EXE**：可通过 `build_exe.py` 构建独立 `.exe`。
  - 单文件可执行程序（无需安装 Python）
  - 包含所有依赖
  - 详见 `BUILD_EXE_CN.md`。

## 🌟 使用场景

- **AI/LLM 项目**：为语言模型生成训练数据索引
- **SEO 团队**：创建全面的 sitemap 以提高搜索引擎可见性
- **内容审计**：发现和编录网站上的所有页面
- **文档站点**：组织和索引技术文档
- **电商网站**：生成产品和类别索引
- **多站点管理**：处理多个子域和语言版本

## 📚 文档

- **[快速开始指南](QUICK_START.md)** - 5 分钟快速上手
- **[GUI 使用指南](docs/gui-usage.md)** - 可视化配置界面
- **[构建 EXE 指南](BUILD_EXE_CN.md)** - 创建独立 Windows 可执行文件
- **[测试指南](docs/testing-guide.md)** - 运行测试和验证配置
- **[路线图](docs/roadmap.md)** - 未来功能和改进

## 🌏 国际化

- **中文**：本文档
- **English**: See [README.md](README.md) and [BUILD_EXE.md](BUILD_EXE.md)

## 🤝 贡献

欢迎贡献！请随时提交 Pull Request。

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🔗 相关项目

- [llms.txt 规范](https://llmstxt.org/) - 官方 llms.txt 格式规范
- [Sitemap 协议](https://www.sitemaps.org/) - XML Sitemap 标准

---

**由 [Thordata](https://www.thordata.com) 用 ❤️ 制作**
