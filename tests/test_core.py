"""
Core test suite for llms-sitemap-generator
Run with: pytest tests/test_core.py -v
"""

import pytest
from pathlib import Path
import sys
import tempfile

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from llms_sitemap_generator.config import (
    AppConfig,
    SiteConfig,
    FiltersConfig,
    OutputConfig,
    SourceConfig,
    FilterRule,
    load_config,
)
from llms_sitemap_generator.validators import (
    validate_url,
    validate_domain,
    validate_language_code,
    validate_config_basic,
)
from llms_sitemap_generator.filters import (
    filter_and_group_urls,
    _detect_language_prefix,
    _auto_group_from_path,
    _compute_score,
)
from llms_sitemap_generator.url_utils import normalize_url, should_skip_by_extension
from llms_sitemap_generator.crawler import _get_url_priority
from llms_sitemap_generator.html_summary import _MetaParser
from llms_sitemap_generator.generator import (
    RenderedPage,
    write_llms_full,
    write_llms_json,
)


class TestConfig:
    def test_site_config_creation(self):
        site = SiteConfig(
            base_url="https://example.com",
            default_language="en",
            allowed_domains=["example.com"],
        )
        assert site.base_url == "https://example.com"
        assert site.default_language == "en"

    def test_output_config_defaults(self):
        output = OutputConfig()
        assert output.llms_txt == "llms.txt"
        assert output.llms_full_txt is None

    def test_source_config_types(self):
        sitemap = SourceConfig(type="sitemap", url="https://example.com/sitemap.xml")
        assert sitemap.type == "sitemap"
        
        crawl = SourceConfig(type="crawl", url="https://example.com", max_depth=3)
        assert crawl.type == "crawl"
        assert crawl.max_depth == 3


class TestValidators:
    def test_validate_url(self):
        assert validate_url("https://example.com")[0] is True
        assert validate_url("not-a-url")[0] is False
        assert validate_url("")[0] is False

    def test_validate_domain(self):
        assert validate_domain("example.com")[0] is True
        assert validate_domain("http://example.com")[0] is False

    def test_validate_language_code(self):
        assert validate_language_code("en")[0] is True
        assert validate_language_code("english")[0] is False

    def test_validate_config_basic(self):
        config = {
            "site": {
                "base_url": "https://example.com",
                "default_language": "en",
            },
            "sources": [
                {"type": "sitemap", "url": "https://example.com/sitemap.xml"},
            ],
        }
        errors = validate_config_basic(config)
        assert len(errors) == 0


class TestFilters:
    def test_detect_language_prefix(self):
        assert _detect_language_prefix("/en/products") == "en"
        assert _detect_language_prefix("/products") is None

    def test_auto_group_from_path(self):
        assert _auto_group_from_path("/") == "Home"
        assert _auto_group_from_path("/blog/article") == "Blog"
        assert _auto_group_from_path("/docs/api") == "Docs"
        assert _auto_group_from_path("/products/item") == "Products"

    def test_compute_score(self):
        score = _compute_score("Products", 100, "/products/item")
        assert score > 0


class TestUrlUtils:
    def test_normalize_url(self):
        assert normalize_url("https://example.com/") == "https://example.com/"
        assert normalize_url("https://example.com/page/") == "https://example.com/page"

    def test_should_skip_by_extension(self):
        assert should_skip_by_extension("https://example.com/image.jpg") is True
        assert should_skip_by_extension("https://example.com/page.html") is False


class TestHtmlSummary:
    def test_meta_parser(self):
        parser = _MetaParser()
        html = "<html><head><title>Test</title></head><body></body></html>"
        parser.feed(html)
        assert parser.title == "Test"


class TestIntegration:
    def test_filter_and_group_urls(self):
        config = AppConfig(
            site=SiteConfig(base_url="https://example.com"),
            sources=[],
            filters=FiltersConfig(
                include=[FilterRule(pattern="^/products", group="Products", priority=100)],
                auto_group=True,
                use_default_excludes=True,
                auto_filter_languages=False,
            ),
            output=OutputConfig(),
        )
        urls = [
            "https://example.com/products/item1",
            "https://example.com/blog/post1",
        ]
        pages = filter_and_group_urls(config, urls)
        assert len(pages) >= 2


class TestOutputs:
    def test_write_llms_full(self):
        config = AppConfig(
            site=SiteConfig(base_url="https://example.com"),
            sources=[],
            filters=FiltersConfig(),
            output=OutputConfig(),
        )
        pages = [
            RenderedPage(
                url="https://example.com/page",
                group="Home",
                path="/page",
                score=100,
                title="Test Page",
                description="Test description",
            )
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "llms-full.txt"
            write_llms_full(config, pages, path)
            assert path.exists()
            content = path.read_text()
            assert "Test Page" in content

    def test_write_llms_json(self):
        config = AppConfig(
            site=SiteConfig(base_url="https://example.com"),
            sources=[],
            filters=FiltersConfig(),
            output=OutputConfig(),
        )
        pages = [
            RenderedPage(
                url="https://example.com/page",
                group="Home",
                path="/page",
                score=100,
                title="Test Page",
                description="Test description",
            )
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "llms.json"
            write_llms_json(config, pages, path)
            assert path.exists()
            import json
            data = json.loads(path.read_text())
            assert data["site"]["base_url"] == "https://example.com"
            assert len(data["pages"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
