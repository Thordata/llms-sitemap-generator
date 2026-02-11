from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import yaml


@dataclass
class SourceConfig:
    type: str
    url: str
    max_depth: int = 2
    max_urls: int = 0  # 0 means fallback to global max_urls
    # for type == "static"
    urls: List[str] = field(default_factory=list)


@dataclass
class FilterRule:
    pattern: str
    group: Optional[str] = None
    priority: int = 0


@dataclass
class ProfileConfig:
    """A named profile that selects which groups to keep for a given run."""

    include_groups: List[str] = field(default_factory=list)


@dataclass
class FiltersConfig:
    include: List[FilterRule] = field(default_factory=list)
    exclude: List[FilterRule] = field(default_factory=list)
    max_urls: int = 2000
    auto_group: bool = True
    profiles: Dict[str, ProfileConfig] = field(default_factory=dict)
    group_limits: Dict[str, int] = field(default_factory=dict)
    default_group_limit: Optional[int] = None
    # 是否启用内置的通用排除规则（如 /search, /tag, /wp-admin 等），默认开启
    use_default_excludes: bool = True
    # 是否启用自动多语言过滤（仅保留 site.default_language 对应的内容），默认开启
    # 如果设为 false，则保留所有语言版本，由用户通过 filters.exclude 手动控制
    auto_filter_languages: bool = True


@dataclass
class OutputConfig:
    llms_txt: str = "llms.txt"
    llms_full_txt: Optional[str] = None
    llms_json: Optional[str] = None
    # 可选：输出标准 sitemap.xml（单文件基础版）
    # 注意：sitemap.xml 默认包含所有收集到的 URL（不过滤），用于 SEO
    # 如果 sitemap_apply_filters=True，则只包含过滤后的 URL（与 llms.txt 一致）
    sitemap_xml: Optional[str] = None
    sitemap_apply_filters: bool = False  # 是否对 sitemap.xml 应用过滤规则
    # 可选：输出 sitemap_index.xml，并按子域拆分子 sitemap（基础版）
    sitemap_index: Optional[str] = None
    generate_full_text: bool = False


@dataclass
class SiteConfig:
    base_url: str
    default_language: str = "en"
    allowed_domains: List[str] = field(default_factory=list)
    description: Optional[str] = None


@dataclass
class AppConfig:
    site: SiteConfig
    sources: List[SourceConfig]
    filters: FiltersConfig
    output: OutputConfig


def _load_raw_config(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping")
    return data


def load_config(path: Path, validate: bool = True) -> AppConfig:
    raw = _load_raw_config(path)

    if "site" not in raw or "base_url" not in raw["site"]:
        raise ValueError("Config `site.base_url` is required")

    base_url = str(raw["site"]["base_url"]).rstrip("/")
    default_language = str(raw["site"].get("default_language", "en"))
    allowed_domains_raw = raw["site"].get("allowed_domains") or []
    if allowed_domains_raw:
        allowed_domains = [str(h).lower() for h in allowed_domains_raw]
    else:
        host = urlparse(base_url).netloc.lower()
        allowed_domains = [host] if host else []

    site = SiteConfig(
        base_url=base_url,
        default_language=default_language,
        allowed_domains=allowed_domains,
        description=str(raw["site"].get("description")) if raw["site"].get("description") is not None else None,
    )

    sources_raw = raw.get("sources") or []
    if not sources_raw:
        raise ValueError("Config `sources` must contain at least one source")
    sources = []
    for s in sources_raw:
        if "type" not in s:
            continue
        stype = str(s["type"])
        url = str(s.get("url", ""))
        urls = [str(u) for u in (s.get("urls") or [])]
        sources.append(
            SourceConfig(
                type=stype,
                url=url,
                max_depth=int(s.get("max_depth", 2)),
                max_urls=int(s.get("max_urls", 0)),
                urls=urls,
            )
        )
    if not sources:
        raise ValueError("Config `sources` must contain valid entries with type and url")

    filters_raw = raw.get("filters") or {}
    include_rules = [
        FilterRule(
            pattern=str(r.get("pattern", "")),
            group=r.get("group"),
            priority=int(r.get("priority", 0)),
        )
        for r in filters_raw.get("include") or []
        if r.get("pattern")
    ]
    exclude_rules = [
        FilterRule(
            pattern=str(r.get("pattern", "")),
            group=r.get("group"),
            priority=int(r.get("priority", 0)),
        )
        for r in filters_raw.get("exclude") or []
        if r.get("pattern")
    ]

    profiles_raw = filters_raw.get("profiles") or {}
    profiles: Dict[str, ProfileConfig] = {}
    for name, pdata in profiles_raw.items():
        include_groups = pdata.get("include_groups") or []
        profiles[name] = ProfileConfig(
            include_groups=[str(g) for g in include_groups],
        )

    group_limits_raw = filters_raw.get("group_limits") or {}
    group_limits: Dict[str, int] = {}
    for gname, limit in group_limits_raw.items():
        try:
            group_limits[str(gname)] = int(limit)
        except Exception:
            continue

    filters = FiltersConfig(
        include=include_rules,
        exclude=exclude_rules,
        max_urls=int(filters_raw.get("max_urls", 1000)),
        auto_group=bool(filters_raw.get("auto_group", True)),
        profiles=profiles,
        group_limits=group_limits,
        default_group_limit=(
            int(filters_raw["default_group_limit"])
            if "default_group_limit" in filters_raw
            else None
        ),
        use_default_excludes=bool(filters_raw.get("use_default_excludes", True)),
        auto_filter_languages=bool(filters_raw.get("auto_filter_languages", True)),
    )

    output_raw = raw.get("output") or {}
    llms_full_txt = output_raw.get("llms_full_txt")
    # 兼容老配置：如果只设置了 generate_full_text，则默认输出 llms-full.txt
    if not llms_full_txt and output_raw.get("generate_full_text"):
        llms_full_txt = "llms-full.txt"

    output = OutputConfig(
        llms_txt=str(output_raw.get("llms_txt", "llms.txt")),
        llms_full_txt=llms_full_txt,
        llms_json=output_raw.get("llms_json"),
        sitemap_xml=output_raw.get("sitemap_xml"),
        sitemap_index=output_raw.get("sitemap_index"),
        generate_full_text=bool(output_raw.get("generate_full_text", False)),
        sitemap_apply_filters=bool(output_raw.get("sitemap_apply_filters", False)),
    )

    return AppConfig(site=site, sources=sources, filters=filters, output=output)

