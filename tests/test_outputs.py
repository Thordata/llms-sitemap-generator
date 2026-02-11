"""
输出与文件生成相关测试

目标：
- 覆盖路线图中的能力：
  - 生成 llms.txt / llms-full.txt / llms.json
  - 生成 sitemap.xml 和 sitemap_index.xml（多子域拆分版）
- 在完全本地、无网络的前提下验证文件结构与基本内容
"""

from __future__ import annotations

from pathlib import Path
import json
import tempfile

from llms_sitemap_generator.config import (
    AppConfig,
    SiteConfig,
    FiltersConfig,
    OutputConfig,
)
from llms_sitemap_generator.generator import (
    RenderedPage,
    write_llms_full,
    write_llms_json,
    _write_sitemaps_and_index,
)


def _make_dummy_config(tmpdir: Path) -> AppConfig:
    """构造一个最小可用的 AppConfig，用于本地输出测试。"""
    site = SiteConfig(
        base_url="https://example.com",
        default_language="en",
        allowed_domains=["example.com", "docs.example.com", "blog.example.com"],
        description="Example site for output tests",
    )
    filters = FiltersConfig(
        max_urls=100,
        auto_group=True,
        use_default_excludes=True,
        auto_filter_languages=True,
    )
    output = OutputConfig(
        llms_txt=str(tmpdir / "llms.txt"),
        llms_full_txt=str(tmpdir / "llms-full.txt"),
        llms_json=str(tmpdir / "llms.json"),
        sitemap_xml=str(tmpdir / "sitemap.xml"),
        sitemap_index=str(tmpdir / "sitemap_index.xml"),
    )
    return AppConfig(site=site, sources=[], filters=filters, output=output)


def _make_dummy_pages() -> list[RenderedPage]:
    """构造一些带有不同子域名的页面，用于 sitemap_index 拆分测试。"""
    urls = [
        "https://example.com/",
        "https://example.com/products",
        "https://docs.example.com/guide",
        "https://docs.example.com/api",
        "https://blog.example.com/post-1",
    ]
    pages: list[RenderedPage] = []
    for idx, u in enumerate(urls, start=1):
        pages.append(
            RenderedPage(
                url=u,
                group="Test",
                path="/",
                score=100 - idx,
                title=f"Page {idx}",
                description=f"Description for {u}",
            )
        )
    return pages


def test_llms_full_and_json_outputs(tmp_path: Path) -> None:
    """测试 llms-full.txt 与 llms.json 输出是否按预期生成且结构正确。"""
    config = _make_dummy_config(tmp_path)
    pages = _make_dummy_pages()

    # 写入 llms-full.txt
    assert config.output.llms_full_txt is not None
    full_path = Path(config.output.llms_full_txt)
    write_llms_full(config, pages, full_path)
    assert full_path.exists()
    text = full_path.read_text(encoding="utf-8")
    # 简单检查：应包含标记和标题
    assert "<|page-1|>" in text
    assert "Page 1" in text

    # 写入 llms.json
    assert config.output.llms_json is not None
    json_path = Path(config.output.llms_json)
    write_llms_json(config, pages, json_path)
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "site" in data
    assert "pages" in data
    assert len(data["pages"]) == len(pages)
    assert data["site"]["base_url"] == config.site.base_url


def test_sitemap_xml_and_index_outputs(tmp_path: Path) -> None:
    """测试 sitemap.xml 与 sitemap_index.xml 生成是否符合预期结构。"""
    config = _make_dummy_config(tmp_path)
    pages = _make_dummy_pages()

    # 使用内部工具生成子域拆分 sitemap + sitemap_index
    assert config.output.sitemap_index is not None
    index_path = Path(config.output.sitemap_index)
    _write_sitemaps_and_index(config, pages, index_path)

    # sitemap_index.xml 应存在
    assert index_path.exists()
    index_content = index_path.read_text(encoding="utf-8")
    assert "<sitemapindex" in index_content
    # 至少应该包含三个 sitemap 条目（example.com / docs.example.com / blog.example.com）
    assert "example.com" in index_content
    assert "docs.example.com" in index_content
    assert "blog.example.com" in index_content

    # 子 sitemap 文件也应该生成
    # 由于 _write_sitemaps_and_index 使用「子域前缀」作为文件名前缀：
    #   - example.com      -> example_sitemap.xml
    #   - docs.example.com -> docs_sitemap.xml
    #   - blog.example.com -> blog_sitemap.xml
    expected_files = [
        tmp_path / "example_sitemap.xml",
        tmp_path / "docs_sitemap.xml",
        tmp_path / "blog_sitemap.xml",
    ]
    for p in expected_files:
        assert p.exists(), f"Expected sitemap file not found: {p}"
        content = p.read_text(encoding="utf-8")
        assert "<urlset" in content
        assert "<loc>" in content

