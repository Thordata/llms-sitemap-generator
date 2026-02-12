# LLMS Sitemap Generator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

**AI-friendly `llms.txt` & sitemap generator** / **面向 LLM 的站点地图生成器**

Automatically collect, filter, and organize website URLs into curated indexes for LLMs and search engines.

自动收集、过滤和组织网站 URL，生成面向 LLM 和搜索引擎的策展式索引。

## ✨ Features / 功能特性

- 🤖 **LLM Training** / **LLM 训练**: Generate `llms.txt` files for AI model training
- 🔍 **SEO Optimization** / **SEO 优化**: Create comprehensive sitemaps
- 📊 **Content Discovery** / **内容发现**: Automatically discover and catalog all pages
- 🌐 **Multi-language** / **多语言**: Smart language filtering
- 🏢 **Enterprise Sites** / **企业网站**: Handle complex B2B SaaS sites with multiple subdomains

## 📦 Installation / 安装

```bash
# Basic / 基础安装
pip install llms-sitemap-generator

# With GUI / 带 GUI 支持
pip install llms-sitemap-generator[gui]
```

## 🎯 Quick Start / 快速开始

### 1. Analyze site / 分析站点

```bash
llms-sitemap-generator analyze https://example.com
```

### 2. Generate / 生成

```bash
# Generate llms.txt / 生成 llms.txt
llms-sitemap-generator generate

# Dry-run / 预览模式
llms-sitemap-generator generate --dry-run --max-pages 100
```

### 3. GUI / 图形界面

```bash
llms-sitemap-generator gui
```

## 📝 Configuration / 配置示例

Minimal `llmstxt.config.yml`:

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
  exclude:
    - pattern: "blog"
  max_urls: 1000
  auto_group: true

output:
  llms_txt: "llms.txt"
  sitemap_xml: "sitemap.xml"
```

## 🛠️ Build Windows EXE / 构建 Windows 可执行文件

```bash
python build_exe.py
```

Output: `dist/llms-sitemap-generator-gui.exe`

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

**Made with ❤️ by [Thordata](https://www.thordata.com)**
