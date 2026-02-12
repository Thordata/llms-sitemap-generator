from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import json
import requests
from urllib.parse import urlparse

from .config import AppConfig
from .filters import PageEntry, filter_and_group_urls, _base_group_weight
from .html_summary import fetch_basic_summary
from .sitemap import collect_urls_from_sources, write_sitemap_xml
from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class RenderedPage:
    url: str
    group: str
    path: str
    score: int
    title: str
    description: str


def _print_summary(pages: List[PageEntry]) -> None:
    total = len(pages)
    logger.info(f"Total pages after filtering: {total}")

    by_group: dict[str, int] = defaultdict(int)
    for p in pages:
        by_group[p.group] += 1

    logger.info("Pages by group:")
    for group, count in sorted(by_group.items(), key=lambda x: (-x[1], x[0])):
        logger.info(f"  - {group}: {count}")

    # Show a small sample for quick inspection
    logger.info("Sample URLs:")
    for p in pages[:10]:
        logger.info(f"  [{p.group}] {p.url}")


def _apply_group_profile(
    config: AppConfig,
    pages: List[PageEntry],
    profile: Optional[str],
    only_groups: Optional[List[str]],
) -> List[PageEntry]:
    """
    Optionally narrow down pages to selected groups based on a named profile
    or an explicit list of groups.
    """
    groups_set: Optional[set[str]] = None

    if only_groups:
        groups_set = set(only_groups)
    elif profile:
        prof = config.filters.profiles.get(profile)
        if not prof:
            logger.warning(f"Profile '{profile}' not found; using all groups.")
        else:
            if "*" in prof.include_groups:
                groups_set = None
            else:
                groups_set = set(prof.include_groups)

    if groups_set is None:
        return pages

    filtered = [p for p in pages if p.group in groups_set]
    logger.info(
        f"Applied group filter; "
        f"{len(filtered)} pages remain in groups: {sorted(groups_set)}"
    )
    return filtered


def generate_llms_txt(
    config: AppConfig,
    output_path: Path,
    *,
    dry_run: bool = False,
    max_pages: Optional[int] = None,
    fetch_content: bool = True,
    profile: Optional[str] = None,
    only_groups: Optional[List[str]] = None,
) -> None:
    """
    End-to-end generation of a basic llms.txt file from configuration:
    - collect URLs from sitemap sources
    - apply include/exclude filters and grouping
    - fetch each page and extract title/meta description
    - render grouped markdown list
    """
    session = requests.Session()

    logger.info("Collecting URLs from sources...")
    urls = collect_urls_from_sources(config, session)
    if not urls:
        logger.warning("No URLs collected from sources. Nothing to do.")
        return

    # 将后续逻辑委托给通用函数，便于 GUI 等场景直接复用已有 URL 列表而不重复爬取
    _generate_llms_from_urls(
        config,
        urls,
        output_path,
        session=session,
        all_urls=urls,
        dry_run=dry_run,
        max_pages=max_pages,
        fetch_content=fetch_content,
        profile=profile,
        only_groups=only_groups,
    )


def generate_llms_from_urls(
    config: AppConfig,
    urls: List[str],
    output_path: Path,
    *,
    dry_run: bool = False,
    max_pages: Optional[int] = None,
    fetch_content: bool = True,
    profile: Optional[str] = None,
    only_groups: Optional[List[str]] = None,
) -> None:
    """
    从**已有 URL 列表**生成 llms.txt / llms-full.txt / llms.json 等输出。
    适用于：
    - GUI 场景已经通过 collect_urls_from_sources 收集并缓存了 URL
    - 想要跳过再次爬取 / 只在内存里重新过滤和生成输出的场景
    """
    session = requests.Session()
    _generate_llms_from_urls(
        config,
        urls,
        output_path,
        session=session,
        all_urls=urls,
        dry_run=dry_run,
        max_pages=max_pages,
        fetch_content=fetch_content,
        profile=profile,
        only_groups=only_groups,
    )


def _generate_llms_from_urls(
    config: AppConfig,
    urls: List[str],
    output_path: Path,
    *,
    session: requests.Session,
    all_urls: Optional[List[str]] = None,
    dry_run: bool = False,
    max_pages: Optional[int] = None,
    fetch_content: bool = True,
    profile: Optional[str] = None,
    only_groups: Optional[List[str]] = None,
) -> None:
    """
    内部通用实现：从 URL 列表到最终输出。
    注意：调用方负责保证 urls 已经是去重和受全局 max_urls 约束的集合。
    """
    # urls 为用于 llms 过滤/分组的 URL 集合，all_urls（如提供）可用于 sitemap.xml 等「不过滤输出」
    logger.info(f"Collected {len(urls)} URLs before filtering.")
    pages: List[PageEntry] = filter_and_group_urls(config, urls)
    if not pages:
        logger.warning("No URLs left after filtering.")
        return

    logger.info(f"{len(pages)} URLs left after filtering.")

    # Apply optional group-based profile / selection
    pages = _apply_group_profile(config, pages, profile=profile, only_groups=only_groups)
    if not pages:
        logger.warning("No URLs left after applying group profile/selection.")
        return

    # Apply per-group limits based on score
    group_limits = config.filters.group_limits
    default_limit = config.filters.default_group_limit
    if group_limits or default_limit:
        by_group: Dict[str, List[PageEntry]] = defaultdict(list)
        for p in pages:
            by_group[p.group].append(p)

        limited_pages: List[PageEntry] = []
        for gname, gpages in by_group.items():
            limit = group_limits.get(gname, default_limit)
            if limit is None or limit <= 0:
                limited_pages.extend(gpages)
                continue
            gpages_sorted = sorted(gpages, key=lambda p: -p.score)
            limited_pages.extend(gpages_sorted[:limit])

        pages = sorted(limited_pages, key=lambda p: (p.group, -p.score, p.path))
        logger.info(f"Applied group limits; {len(pages)} pages remain.")

    if max_pages is not None and max_pages > 0:
        pages = pages[:max_pages]
        logger.info(f"Truncated to first {len(pages)} pages due to max_pages={max_pages}.")

    if dry_run:
        _print_summary(pages)
        return

    # Group pages by group name
    groups: dict[str, List[PageEntry]] = defaultdict(list)
    for p in pages:
        groups[p.group].append(p)

    lines: List[str] = []
    rendered_pages: List[RenderedPage] = []
    
    # Title format: Simple, only show domain (clean format)
    lines.append(f"# {config.site.base_url}")
    lines.append("")

    # Site Overview at top (using blockquote format)
    if config.site.description:
        # Use > blockquote format for better readability
        desc_lines = config.site.description.strip().split("\n")
        for line in desc_lines:
            if line.strip():
                lines.append(f" > {line.strip()}")
        lines.append("")

    # Detailed group list, avoid duplicate URLs (e.g. with/without trailing slash)
    seen_url_keys: set[tuple[str, str, str]] = set()
    # Used to count actual output pages per group after deduplication
    actual_group_counts: Dict[str, int] = defaultdict(int)

    def _url_key(u: str) -> tuple[str, str]:
        """
        Canonical URL key for dedup:
        - Treat http/https as the same
        - Ignore fragment
        - Strip trailing slash (except root)
        """
        parsed = urlparse(u)
        host = parsed.netloc.lower()
        path = parsed.path or "/"
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        return host, path

    def _group_sort_key(name: str) -> tuple[int, str]:
        return (-_base_group_weight(name), name)

    # First pass: count actual numbers after deduplication
    for group_name in sorted(groups.keys(), key=_group_sort_key):
        for p in groups[group_name]:
            key = _url_key(p.url)
            if key not in seen_url_keys:
                seen_url_keys.add(key)
                actual_group_counts[group_name] += 1

    # Clear seen_url_keys, prepare for actual output
    seen_url_keys.clear()

    # Group statistics overview using deduplicated counts
    # Note: Groups Overview is not displayed, directly show groups (cleaner format)
    # lines.append("## Groups Overview")
    # lines.append("")
    # for g in sorted(actual_group_counts.keys(), key=_group_sort_key):
    #     lines.append(f"- {g}: {actual_group_counts[g]} pages")
    # lines.append("")

    # Detailed group list output (clean format)
    for group_name in sorted(groups.keys(), key=_group_sort_key):
        # Use simpler group title format
        lines.append(f"## {group_name}")
        lines.append("")
        for p in groups[group_name]:
            key = _url_key(p.url)
            if key in seen_url_keys:
                continue
            seen_url_keys.add(key)
            if fetch_content:
                # Extract site name from base URL for description generation
                base_parsed = urlparse(config.site.base_url)
                site_name = base_parsed.netloc.replace("www.", "").split(".")[0].title() if base_parsed.netloc else None
                title, desc = fetch_basic_summary(p.url, session, site_name=site_name)
            else:
                title = p.url
                desc = f"Page at {p.url}"
            lines.append(f"- [{title}]({p.url}): {desc}")
            rendered_pages.append(
                RenderedPage(
                    url=p.url,
                    group=group_name,
                    path=p.path,
                    score=p.score,
                    title=title,
                    description=desc,
                )
            )
        lines.append("")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Wrote llms.txt to {output_path}")

    # Optional additional outputs
    if config.output.llms_full_txt:
        full_path = Path(config.output.llms_full_txt)
        # If relative path, make it relative to output_path's parent
        if not full_path.is_absolute():
            full_path = output_path.parent / full_path
        write_llms_full(config, rendered_pages, full_path)
    if config.output.llms_json:
        json_path = Path(config.output.llms_json)
        # If relative path, make it relative to output_path's parent
        if not json_path.is_absolute():
            json_path = output_path.parent / json_path
        write_llms_json(config, rendered_pages, json_path)
    if config.output.sitemap_xml:
        # sitemap.xml:
        # - 默认包含所有已收集到的 URL（不应用过滤），用于 SEO
        # - 若 sitemap_apply_filters=True，则仅包含最终筛选后的 URL（与 llms.txt 一致）
        if config.output.sitemap_apply_filters:
            sitemap_urls = [p.url for p in rendered_pages]
            logger.info(
                f"Generating sitemap.xml with filtered URLs ({len(sitemap_urls)} URLs)"
            )
        else:
            # 优先复用调用方提供的 all_urls，避免为生成 sitemap 再次触发完整收集/爬虫
            if all_urls is not None:
                sitemap_urls = list(all_urls)
                logger.info(
                    f"Generating sitemap.xml with previously collected URLs "
                    f"({len(sitemap_urls)} URLs)"
                )
            else:
                sitemap_urls = collect_urls_from_sources(config, session)
                logger.info(
                    "Generating sitemap.xml with all collected URLs "
                    f"({len(sitemap_urls)} URLs)"
                )
        sitemap_path = config.output.sitemap_xml
        # If relative path, make it relative to output_path's parent
        sitemap_path_obj = Path(sitemap_path)
        if not sitemap_path_obj.is_absolute():
            sitemap_path_obj = output_path.parent / sitemap_path_obj
        write_sitemap_xml(config, sitemap_urls, str(sitemap_path_obj))
    if config.output.sitemap_index:
        # sitemap_index should include all URLs (all languages), not just filtered ones
        if all_urls is not None:
            sitemap_index_urls = list(all_urls)
        else:
            sitemap_index_urls = collect_urls_from_sources(config, session)
        index_path = Path(config.output.sitemap_index)
        # If relative path, make it relative to output_path's parent
        if not index_path.is_absolute():
            index_path = output_path.parent / index_path
        _write_sitemaps_and_index(config, sitemap_index_urls, index_path)


def _write_sitemaps_and_index(
    config: AppConfig,
    urls: List[str],  # Changed from List[RenderedPage] to List[str] to accept all URLs
    index_path: Path,
) -> None:
    """
    Basic version: Split sitemap by subdomain and generate sitemap_index.xml.
    - One sitemap file per subdomain, e.g. www_sitemap.xml / doc_sitemap.xml
    - <loc> in index file uses corresponding subdomain as host, files located at root path.
    - Includes all URLs (all languages) for SEO purposes.
    """
    by_host: Dict[str, List[str]] = defaultdict(list)
    for url in urls:
        u = urlparse(url)
        host = (u.netloc or "").lower()
        if not host:
            continue
        by_host[host].append(url)

    if not by_host:
        logger.warning("No hosts found for sitemap_index; skipping.")
        return

    # Ensure output directory exists
    index_path.parent.mkdir(parents=True, exist_ok=True)
    base_dir = index_path.parent

    sitemap_entries: List[Dict[str, str]] = []
    for host, urls in sorted(by_host.items()):
        # Use subdomain prefix as filename prefix, e.g. www_sitemap.xml / doc_sitemap.xml
        sub = host.split(".")[0] if "." in host else host or "site"
        sitemap_filename = f"{sub}_sitemap.xml"
        sitemap_path = base_dir / sitemap_filename

        # Reuse basic sitemap generation logic
        write_sitemap_xml(config, urls, str(sitemap_path))

        scheme = "https" if not urls else (urlparse(urls[0]).scheme or "https")
        loc = f"{scheme}://{host}/{sitemap_filename}"
        sitemap_entries.append(
            {
                "loc": loc,
            }
        )

    # Generate sitemap_index.xml
    from xml.etree import ElementTree as ET  # Local import to avoid top-level dependency

    root = ET.Element(
        "sitemapindex",
        attrib={"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"},
    )

    today = datetime.now(timezone.utc).date().isoformat()
    for entry in sitemap_entries:
        sm_el = ET.SubElement(root, "sitemap")
        loc_el = ET.SubElement(sm_el, "loc")
        loc_el.text = entry["loc"]
        lastmod_el = ET.SubElement(sm_el, "lastmod")
        lastmod_el.text = today

    tree = ET.ElementTree(root)
    index_path.write_text(
        ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8"),
        encoding="utf-8",
    )
    logger.info(f"Wrote sitemap_index.xml to {index_path}")


def write_llms_full(config: AppConfig, pages: List[RenderedPage], path: Path) -> None:
    # Ensure output directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append(f"# {config.site.base_url} llms-full.txt")
    lines.append("# Generated by llms-sitemap-generator")
    lines.append(f"# Default language: {config.site.default_language}")
    lines.append("")

    for idx, p in enumerate(pages, start=1):
        lines.append(f"<|page-{idx}|>")
        lines.append(f"## {p.title}")
        lines.append(f"URL: {p.url}")
        lines.append(f"Group: {p.group}")
        lines.append(f"Score: {p.score}")
        lines.append("")
        lines.append(p.description)
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Wrote llms-full.txt to {path}")


def write_llms_json(config: AppConfig, pages: List[RenderedPage], path: Path) -> None:
    # Ensure output directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "site": {
            "base_url": config.site.base_url,
            "default_language": config.site.default_language,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tool": "llms-sitemap-generator",
        },
        "pages": [
            {
                "url": p.url,
                "group": p.group,
                "path": p.path,
                "score": p.score,
                "title": p.title,
                "description": p.description,
            }
            for p in pages
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Wrote llms.json to {path}")

