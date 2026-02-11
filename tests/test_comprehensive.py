"""
Comprehensive test suite for llms-sitemap-generator
使用 pytest 运行: pytest tests/ -v
"""

import pytest
from pathlib import Path
import sys
import tempfile

# 确保 src 在路径中
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from llms_sitemap_generator.config import (
    AppConfig,
    SiteConfig,
    FiltersConfig,
    OutputConfig,
    SourceConfig,
    FilterRule,
    ProfileConfig,
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
    PageEntry,
    _detect_language_prefix,
    _auto_group_from_path,
    _compute_score,
)
from llms_sitemap_generator.url_utils import normalize_url, should_skip_by_extension
from llms_sitemap_generator.crawler import _get_url_priority
from llms_sitemap_generator.html_summary import _MetaParser


class TestConfig:
    """测试配置模块"""

    def test_site_config_creation(self):
        """测试 SiteConfig 创建"""
        site = SiteConfig(
            base_url="https://example.com",
            default_language="en",
            allowed_domains=["example.com"],
            description="Test site",
        )
        assert site.base_url == "https://example.com"
        assert site.default_language == "en"
        assert "example.com" in site.allowed_domains

    def test_output_config_defaults(self):
        """测试 OutputConfig 默认值"""
        output = OutputConfig()
        assert output.llms_txt == "llms.txt"
        assert output.llms_full_txt is None
        assert output.llms_json is None
        assert output.sitemap_xml is None
        assert output.sitemap_apply_filters is False

    def test_source_config_sitemap(self):
        """测试 SourceConfig sitemap 类型"""
        source = SourceConfig(type="sitemap", url="https://example.com/sitemap.xml")
        assert source.type == "sitemap"
        assert source.url == "https://example.com/sitemap.xml"

    def test_source_config_crawl(self):
        """测试 SourceConfig crawl 类型"""
        source = SourceConfig(
            type="crawl", url="https://example.com/blog", max_depth=3, max_urls=500
        )
        assert source.type == "crawl"
        assert source.max_depth == 3
        assert source.max_urls == 500

    def test_source_config_static(self):
        """测试 SourceConfig static 类型"""
        # static 类型仍然需要 url 字段（用于标识来源）
        source = SourceConfig(
            type="static",
            url="static://manual",  # url 是必需字段
            urls=["https://example.com/page1", "https://example.com/page2"],
        )
        assert source.type == "static"
        assert len(source.urls) == 2


class TestValidators:
    """测试验证器模块"""

    def test_validate_url_valid(self):
        """测试有效 URL 验证"""
        is_valid, error = validate_url("https://example.com")
        assert is_valid is True
        assert error == ""

    def test_validate_url_invalid(self):
        """测试无效 URL 验证"""
        is_valid, error = validate_url("not-a-url")
        assert is_valid is False
        assert error != ""

    def test_validate_url_empty(self):
        """测试空 URL 验证"""
        is_valid, error = validate_url("")
        assert is_valid is False

    def test_validate_domain_valid(self):
        """测试有效域名验证"""
        is_valid, error = validate_domain("example.com")
        assert is_valid is True

    def test_validate_domain_with_protocol(self):
        """测试带协议的域名验证"""
        is_valid, error = validate_domain("https://example.com")
        assert is_valid is False

    def test_validate_language_code_valid(self):
        """测试有效语言代码"""
        is_valid, error = validate_language_code("en")
        assert is_valid is True
        is_valid, error = validate_language_code("zh")
        assert is_valid is True

    def test_validate_language_code_invalid(self):
        """测试无效语言代码"""
        is_valid, error = validate_language_code("english")
        assert is_valid is False

    def test_validate_config_basic_valid(self):
        """测试有效配置验证"""
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

    def test_validate_config_basic_missing_site(self):
        """测试缺少 site 配置"""
        config = {"sources": []}
        errors = validate_config_basic(config)
        assert len(errors) > 0

    def test_validate_config_basic_missing_sources(self):
        """测试缺少 sources 配置"""
        config = {"site": {"base_url": "https://example.com"}}
        errors = validate_config_basic(config)
        assert len(errors) > 0


class TestFilters:
    """测试过滤模块"""

    def test_detect_language_prefix(self):
        """测试语言前缀检测"""
        assert _detect_language_prefix("/en/products") == "en"
        assert _detect_language_prefix("/zh-hk/page") == "zh"
        assert _detect_language_prefix("/doc/zh-cn/help") == "zh"
        assert _detect_language_prefix("/products/pricing") is None

    def test_auto_group_from_path_home(self):
        """测试首页分组"""
        assert _auto_group_from_path("/") == "Home"

    def test_auto_group_from_path_blog(self):
        """测试 Blog 分组"""
        assert _auto_group_from_path("/blog/article") == "Blog"
        assert _auto_group_from_path("/posts/guide") == "Blog"

    def test_auto_group_from_path_docs(self):
        """测试 Docs 分组"""
        assert _auto_group_from_path("/docs/api") == "Docs"
        assert _auto_group_from_path("/documentation/guide") == "Docs"

    def test_auto_group_from_path_products(self):
        """测试 Products 分组"""
        assert _auto_group_from_path("/products/item") == "Products"
        assert _auto_group_from_path("/solutions/enterprise") == "Products"

    def test_compute_score(self):
        """测试重要性评分"""
        score = _compute_score("Products", 100, "/products/item")
        assert score > 0
        # Home page should have bonus
        home_score = _compute_score("Home", 0, "/")
        assert home_score > 0


class TestUrlUtils:
    """测试 URL 工具模块"""

    def test_normalize_url(self):
        """测试 URL 规范化"""
        # Root path should keep trailing slash
        assert normalize_url("https://example.com/") == "https://example.com/"
        # Non-root paths should have trailing slash removed
        assert normalize_url("https://example.com/page/") == "https://example.com/page"
        assert normalize_url("https://example.com/page") == "https://example.com/page"

    def test_should_skip_by_extension(self):
        """测试文件扩展名跳过"""
        assert should_skip_by_extension("https://example.com/image.jpg") is True
        assert should_skip_by_extension("https://example.com/page.html") is False
        assert should_skip_by_extension("https://example.com/doc.pdf") is True


class TestCrawler:
    """测试爬虫模块"""

    def test_get_url_priority(self):
        """测试 URL 优先级计算"""
        assert _get_url_priority("https://example.com/products/item") == 3
        assert _get_url_priority("https://example.com/pricing") == 3
        assert _get_url_priority("https://example.com/blog/post") == 2
        assert _get_url_priority("https://example.com/careers") == 0


class TestHtmlSummary:
    """测试 HTML 摘要模块"""

    def test_meta_parser_title(self):
        """测试 Meta 解析器标题提取"""
        parser = _MetaParser()
        html = "<html><head><title>Test Title</title></head><body></body></html>"
        parser.feed(html)
        assert parser.title == "Test Title"

    def test_meta_parser_description(self):
        """测试 Meta 解析器描述提取"""
        parser = _MetaParser()
        html = '<html><head><meta name="description" content="Test description"></head><body></body></html>'
        parser.feed(html)
        assert parser.description == "Test description"

    def test_meta_parser_h1(self):
        """测试 Meta 解析器 h1 提取"""
        parser = _MetaParser()
        html = "<html><body><h1>Main Heading</h1></body></html>"
        parser.feed(html)
        assert parser.h1 == "Main Heading"


class TestIntegration:
    """集成测试 - 测试完整的过滤流程"""

    def test_filter_and_group_urls_basic(self):
        """测试基本过滤和分组"""
        config = AppConfig(
            site=SiteConfig(base_url="https://example.com"),
            sources=[],
            filters=FiltersConfig(
                include=[
                    FilterRule(pattern="^/products", group="Products", priority=100),
                ],
                auto_group=True,
                use_default_excludes=True,
                auto_filter_languages=False,
            ),
            output=OutputConfig(),
        )

        urls = [
            "https://example.com/products/item1",
            "https://example.com/products/item2",
            "https://example.com/blog/post1",
            "https://example.com/about",
        ]

        pages = filter_and_group_urls(config, urls)

        # Should have 4 pages (include rule for products, auto-group for others)
        assert len(pages) == 4

        # Check that products have higher priority
        product_pages = [p for p in pages if p.group == "Products"]
        assert len(product_pages) == 2
        assert product_pages[0].priority == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
