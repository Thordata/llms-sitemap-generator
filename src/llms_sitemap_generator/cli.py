import argparse
import sys
from pathlib import Path

from .config import load_config
from .generator import generate_llms_txt


DEFAULT_CONFIG_NAME = "llmstxt.config.yml"


def cmd_init(args):
    """Create a starter config file in the current directory."""
    target = Path(args.path or DEFAULT_CONFIG_NAME)
    if target.exists() and not args.force:
        print(f"[WARN] Config file already exists: {target}", file=sys.stderr)
        return 1

    template = f"""# LLMS Sitemap Generator config
#
# 你通常只需要改这几个地方：
# 1）site.base_url      —— 你的网站主域名
# 2）sources            —— sitemap 或起始爬取 URL
# 3）filters.include    —— 想重点保留的路径段（产品 / 文档 / 定价等）
# 4）filters.exclude    —— 明确不要的路径段（博客 / 招聘 / 新闻等）

site:
  base_url: "https://example.com"
  default_language: "en"

sources:
  # 优先推荐：直接从 sitemap 导入 URL（如有 sitemap.xml）
  - type: "sitemap"
    url: "https://example.com/sitemap.xml"

  # 备用方案：没有 sitemap 时，从首页或文档入口做爬取
  # - type: "crawl"
  #   url: "https://example.com/"
  #   max_depth: 2
  #   max_urls: 1000

filters:
  include:
    # 示例：产品
    - pattern: "^/products"
      group: "Products"
      priority: 100

    # 示例：文档
    - pattern: "^/docs"
      group: "Docs"
      priority: 90

    # 示例：定价
    - pattern: "^/pricing"
      group: "Pricing"
      priority: 80

  exclude:
    # 示例：博客 / 新闻 / 招聘 等通常不希望进入 llms.txt 的内容
    - pattern: "blog"
    - pattern: "news"
    - pattern: "^/careers"

        # 全站最多保留的 URL 数量（在 include/exclude 之后）
        # 建议控制在 500~2000 之间，保证 llms.txt 更「精选」
        max_urls: 1000

  # 自动按路径首段分组，如 /products/... -> "Products"
  auto_group: true

  # 每个分组的最大条数（按 score 排序截断）
  group_limits:
    Products: 100
    Docs: 200
    Pricing: 50

  # 内置一些通用排除规则（如 /search, /wp-admin 等），通常不需要改
  use_default_excludes: true

output:
  llms_txt: "llms.txt"
  # 可选：输出更长的 llms-full.txt 与 JSON
  llms_full_txt: "llms-full.txt"
  llms_json: "llms.json"
  # 可选：输出标准 sitemap.xml
  sitemap_xml: "sitemap.xml"
"""
    target.write_text(template, encoding="utf-8")
    print(f"[OK] Created config file: {target}")
    return 0


def cmd_generate(args):
    """Placeholder for generate command (will implement sitemap & llms.txt soon)."""
    config_path = Path(args.config or DEFAULT_CONFIG_NAME)
    if not config_path.exists():
        print(
            f"[ERROR] Config file not found: {config_path}. "
            f"Run `llms-sitemap-generator init` first.",
            file=sys.stderr,
        )
        return 1

    try:
        # 默认启用验证，但可以通过 --no-validate 跳过
        validate = not getattr(args, "no_validate", False)
        config = load_config(config_path, validate=validate)
    except ValueError as e:
        # 配置验证错误，提供更友好的提示
        print(f"[ERROR] 配置验证失败:", file=sys.stderr)
        print(f"{e}", file=sys.stderr)
        print(f"\n提示: 使用 --no-validate 可以跳过验证（不推荐）", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] Failed to load config: {e}", file=sys.stderr)
        return 1

    output_path = Path(config.output.llms_txt)

    only_groups_list = None
    if getattr(args, "only_groups", None):
        only_groups_list = [g.strip() for g in args.only_groups.split(",") if g.strip()]

    generate_llms_txt(
        config,
        output_path,
        dry_run=bool(getattr(args, "dry_run", False)),
        max_pages=getattr(args, "max_pages", None),
        fetch_content=not bool(getattr(args, "no_fetch", False)),
        profile=getattr(args, "profile", None),
        only_groups=only_groups_list,
    )
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="llms-sitemap-generator",
        description="AI-friendly llms.txt & sitemap generator for websites.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser(
        "init", help="Create a starter llmstxt.config.yml in current directory."
    )
    p_init.add_argument(
        "-p",
        "--path",
        help=f"Config file path (default: {DEFAULT_CONFIG_NAME})",
    )
    p_init.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing config file.",
    )
    p_init.set_defaults(func=cmd_init)

    # generate
    p_gen = subparsers.add_parser(
        "generate",
        help="Generate llms.txt (and later sitemap, llms-full.txt, etc.).",
    )
    p_gen.add_argument(
        "-c",
        "--config",
        help=f"Config file path (default: {DEFAULT_CONFIG_NAME})",
    )
    p_gen.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write files; only print counts and sample URLs after filtering.",
    )
    p_gen.add_argument(
        "--max-pages",
        type=int,
        help="Limit the number of pages processed after filtering (for quick tests).",
    )
    p_gen.add_argument(
        "--no-fetch",
        action="store_true",
        help="Do not fetch page content; use URL as title and a generic description.",
    )
    p_gen.add_argument(
        "--profile",
        help="Named profile from config.filters.profiles to select which groups to keep.",
    )
    p_gen.add_argument(
        "--only-groups",
        help="Comma-separated list of groups to keep (overrides profile).",
    )
    p_gen.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip configuration validation (not recommended).",
    )
    p_gen.set_defaults(func=cmd_generate)

    # analyze command
    p_analyze = subparsers.add_parser(
        "analyze",
        help="Analyze website structure and recommend optimal configuration (smart setup)",
    )
    p_analyze.add_argument(
        "url",
        help="Base URL of the website to analyze (e.g., https://example.com)",
    )
    p_analyze.add_argument(
        "-o",
        "--output",
        help="Output config file path (default: llmstxt.config.yml)",
    )
    p_analyze.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing config file if it exists.",
    )
    p_analyze.set_defaults(func=cmd_analyze)

    # gui command
    p_gui = subparsers.add_parser("gui", help="Launch the GUI tool (requires PyQt5)")
    p_gui.set_defaults(func=cmd_gui)

    return parser


def cmd_analyze(args):
    """Analyze website and generate recommended configuration."""
    import requests
    import yaml
    from .site_analyzer import recommend_config

    url = args.url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    print(f"[INFO] Analyzing website: {url}")
    print("[INFO] This may take a minute...")

    try:
        session = requests.Session()
        recommendations = recommend_config(url, session)

        # Generate config YAML
        config_data = {
            "site": recommendations["site"],
            "sources": recommendations["sources"],
            "filters": recommendations["filters"],
            "output": {
                "llms_txt": "llms.txt",
                "llms_full_txt": "llms-full.txt",
                "llms_json": "llms.json",
                "sitemap_xml": "sitemap.xml",
            },
        }

        # Determine output path
        output_path = Path(args.output or DEFAULT_CONFIG_NAME)

        # Check if file exists
        if output_path.exists() and not args.force:
            print(
                f"[WARN] Config file already exists: {output_path}",
                file=sys.stderr,
            )
            print(
                "[INFO] Use -f/--force to overwrite or specify a different path with -o",
                file=sys.stderr,
            )
            return 1

        # Write config file
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)

        print(f"\n[OK] Recommended configuration written to: {output_path}")
        print("\n[USAGE] To generate llms.txt, run:")
        print(f"  llms-sitemap-generator generate -c {output_path}")
        return 0

    except Exception as e:
        print(f"[ERROR] Analysis failed: {e}", file=sys.stderr)
        return 1


def cmd_gui(args):
    """Launch the simplified smart GUI tool."""
    try:
        from .gui_main import main as gui_main

        gui_main()
        return 0
    except ImportError as e:
        # 显示具体的导入错误，帮助诊断问题
        import traceback

        print(
            f"[ERROR] Failed to import GUI module: {e}",
            file=sys.stderr,
        )
        print(
            "[DEBUG] Detailed traceback:",
            file=sys.stderr,
        )
        traceback.print_exc()
        print(
            "\n[INFO] Please ensure PyQt5 is installed: pip install PyQt5",
            file=sys.stderr,
        )
        print(
            "[INFO] Or install GUI dependencies: pip install -r requirements-gui.txt",
            file=sys.stderr,
        )
        return 1


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1

    return int(func(args)) or 0


if __name__ == "__main__":
    raise SystemExit(main())
