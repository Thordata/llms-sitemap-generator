# LLMS Sitemap Generator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://badge.fury.io/py/llms-sitemap-generator.svg)](https://badge.fury.io/py/llms-sitemap-generator)

**AI-friendly `llms.txt` & sitemap generator for websites** - Automatically collect, filter, and organize website URLs into curated indexes for LLMs and search engines.

Generate SEO-friendly sitemaps and LLM-optimized `llms.txt` files for any website, from simple blogs to complex B2B SaaS platforms. Works with sitemaps, crawling, or manual URL lists. Includes a visual GUI tool and supports Windows .exe builds.

## ✨ Key Features

**Perfect for:**
- 🤖 **LLM Training**: Generate `llms.txt` files for AI model training and RAG systems
- 🔍 **SEO Optimization**: Create comprehensive sitemaps for search engine indexing
- 📊 **Content Discovery**: Automatically discover and catalog all website pages
- 🌐 **Multi-language Sites**: Smart language filtering for international websites
- 🏢 **Enterprise Sites**: Handle complex B2B SaaS sites with multiple subdomains

## 🚀 Features

- **Universal & Easy to Use**
  - Works for any website: from simple blogs to complex B2B SaaS sites
  - Simple configuration with smart defaults
  - GUI tool for visual configuration (no coding required)
- **URL Sources**
  - Import from `sitemap.xml` (supports sitemap index)
  - Crawl from homepage or any entry URL when no sitemap is available
  - Auto-discover subdomains from sitemap
  - Static URL lists for manual additions
- **Filtering & Grouping**
  - Include / exclude URL rules with regex patterns
  - Automatic grouping by path segments (Home / Products / Docs / Pricing / Blog / etc.)
  - Language filtering: `llms.txt` for default language, `sitemap.xml` for all languages
  - Optional profiles to define different tiers (minimal / recommended / full)
  - Per-group limits to control output size
- **Output Formats**
  - `llms.txt`: curated, grouped Markdown index for LLMs (oxlabs.io format compatible)
  - `llms-full.txt`: detailed version with extra metadata (optional)
  - `llms.json`: structured JSON with all pages (optional)
  - `sitemap.xml` & `sitemap_index.xml`: SEO-friendly sitemaps with all languages (optional)

## 📦 Installation

```bash
# Basic installation
pip install llms-sitemap-generator

# With GUI support (optional)
pip install llms-sitemap-generator[gui]
```

## 🎯 Quickstart

```bash
pip install llms-sitemap-generator

llms-sitemap-generator --help
```

### 1. Initialize or analyze a site

Create a starter config in the current directory:

```bash
llms-sitemap-generator init
```

Or let the tool analyze your site and generate a recommended config:

```bash
llms-sitemap-generator analyze https://example.com
```

### 2. Generate `llms.txt`

After editing `llmstxt.config.yml` for your website:

```bash
# Quick dry-run (no file writes, useful to inspect grouping)
llms-sitemap-generator generate --dry-run --max-pages 100

# Normal run: generate llms.txt and optional extra outputs
llms-sitemap-generator generate

# Faster testing without fetching page content
llms-sitemap-generator generate --no-fetch
```

### 3. Control output size & sections

Use profiles (defined in `filters.profiles`) to switch between minimal / recommended / full tiers:

```bash
llms-sitemap-generator generate --profile minimal
llms-sitemap-generator generate --profile recommended
llms-sitemap-generator generate --profile full
```

Or temporarily keep only specific groups (overrides profile):

```bash
llms-sitemap-generator generate --only-groups "Home,Products"
```

## Basic Configuration

Minimal `llmstxt.config.yml` example:

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

  # Global limit after filtering (keeps llms.txt focused)
  max_urls: 1000
  auto_group: true

output:
  llms_txt: "llms.txt"
  llms_full_txt: "llms-full.txt"
  llms_json: "llms.json"
  sitemap_xml: "sitemap.xml"
  sitemap_index: "sitemap_index.xml"
```

## CLI Commands

- **`llms-sitemap-generator init`**: create a starter `llmstxt.config.yml`.
- **`llms-sitemap-generator analyze URL`**: analyze a site and generate a recommended config.
- **`llms-sitemap-generator generate`**: generate `llms.txt` (+ optional extra outputs).
- **`llms-sitemap-generator gui`**: launch the optional GUI (requires `PyQt5`).

## Optional GUI & Windows EXE

- **GUI**: run `llms-sitemap-generator gui` after installing with `pip install llms-sitemap-generator[gui]`. 
  - Visual configuration interface
  - Real-time URL collection and preview
  - Subdomain discovery and selection
  - Group selection and filtering
  - See `docs/gui-usage.md` for details.
- **Windows EXE**: you can build a standalone `.exe` using `build_exe.py`. 
  - Single-file executable (no Python required)
  - Includes all dependencies
  - See `BUILD_EXE.md` for detailed instructions.

## 🌟 Use Cases

- **AI/LLM Projects**: Generate training data indexes for language models
- **SEO Teams**: Create comprehensive sitemaps for better search engine visibility
- **Content Audits**: Discover and catalog all pages on your website
- **Documentation Sites**: Organize and index technical documentation
- **E-commerce Sites**: Generate product and category indexes
- **Multi-site Management**: Handle multiple subdomains and language versions

## 📚 Documentation

- **[Quick Start Guide](QUICK_START.md)** - Get started in 5 minutes
- **[GUI Usage Guide](docs/gui-usage.md)** - Visual configuration interface
- **[Build EXE Guide](BUILD_EXE.md)** - Create standalone Windows executable
- **[Testing Guide](docs/testing-guide.md)** - Run tests and validate configuration
- **[Roadmap](docs/roadmap.md)** - Future features and improvements

## 🌏 Internationalization

- **English**: This README
- **中文 (Chinese)**: See [README_CN.md](README_CN.md) and [BUILD_EXE_CN.md](BUILD_EXE_CN.md)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related Projects

- [llms.txt specification](https://llmstxt.org/) - Official llms.txt format specification
- [Sitemap Protocol](https://www.sitemaps.org/) - XML Sitemap standard

---

**Made with ❤️ by [Thordata](https://www.thordata.com)**
