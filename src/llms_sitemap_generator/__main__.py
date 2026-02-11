"""
Entry point for running the package as a module:
    python -m llms_sitemap_generator
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
