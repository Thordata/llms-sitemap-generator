# LLMS Sitemap Generator - Quick Start

## Install

```bash
pip install llms-sitemap-generator
```

Optional GUI:

```bash
pip install llms-sitemap-generator[gui]
```

## 1. Get a config

Analyze a site and auto-generate `llmstxt.config.yml`:

```bash
llms-sitemap-generator analyze https://example.com
```

Or create a minimal starter config in the current directory:

```bash
llms-sitemap-generator init
```

## 2. Generate `llms.txt`

```bash
# Using default config (llmstxt.config.yml)
llms-sitemap-generator generate

# Use another config file
llms-sitemap-generator generate -c my-config.yml

# Dry-run with limited pages (no files written)
llms-sitemap-generator generate --dry-run --max-pages 100

# Skip fetching page content (faster experiments)
llms-sitemap-generator generate --no-fetch
```

## 3. Outputs

After a normal run, you typically get:

| File | Description |
|------|-------------|
| `llms.txt` | Main curated index for LLMs (grouped Markdown) |
| `llms-full.txt` | Longer version with extra metadata (if enabled in config) |
| `llms.json` | Structured JSON with all pages (if enabled) |
| `sitemap.xml` | Standard sitemap with all URLs (if enabled) |
| `sitemap_index.xml` | Multi-subdomain sitemap index (if enabled) |

## 4. Minimal config example

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

  max_urls: 1000
  auto_group: true

output:
  llms_txt: "llms.txt"
  llms_full_txt: "llms-full.txt"
  llms_json: "llms.json"
  sitemap_xml: "sitemap.xml"
```

## 5. More

- See `README.md` for full documentation and advanced configuration.
- Run `llms-sitemap-generator generate --help` to view all CLI options.
