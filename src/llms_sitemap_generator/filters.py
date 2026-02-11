from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse

from .config import AppConfig, FilterRule


@dataclass
class PageEntry:
    url: str
    path: str
    group: str
    priority: int
    score: int


def _relative_path(base_url: str, url: str) -> str:
    base = urlparse(base_url)
    u = urlparse(url)
    path = u.path or "/"
    return path


def _detect_language_prefix(path: str) -> Optional[str]:
    """
    Roughly detect language code from path, e.g.:
    - "/en/products/..." -> "en"
    - "/doc/zh-hk/page/..."  -> "zh"
    - "/zh-cn/blog/..." -> "zh"
    Only used to distinguish default language prefix, not strict i18n parsing.
    """
    # First try to match at the beginning of the path
    m = re.match(r"^/([a-z]{2})(?:[-_][a-zA-Z]{2})?/", path)
    if m:
        return m.group(1).lower()

    # Also search for language codes anywhere in the path
    # This handles cases like /doc/zh-hk/page or /help/en-us/article
    m = re.search(r"/([a-z]{2})(?:[-_][a-zA-Z]{2})?/", path)
    if m:
        return m.group(1).lower()

    return None


def _match_rule(path: str, rule: FilterRule) -> bool:
    return re.search(rule.pattern, path) is not None


def _auto_group_from_path(path: str) -> str:
    """
    Heuristic grouping: use first non-empty path segment as group name.
    e.g. "/products/abc" -> "Products", "/pricing" -> "Pricing", "/blog/xxx" -> "Blog".
    Handles language prefixes: "/vi/products/abc" -> "Products", "/zh-hk/blog/xxx" -> "Blog".
    """
    if path == "/":
        return "Home"
    segments = [seg for seg in path.split("/") if seg]
    if not segments:
        return "Other"
    
    # Check if first segment is a language code (2-letter code, optionally followed by -xx)
    first = segments[0].lower()
    lang_match = re.match(r"^[a-z]{2}(?:[-_][a-zA-Z]{2})?$", first)
    
    # If first segment is a language code, use the second segment for grouping
    if lang_match and len(segments) > 1:
        first = segments[1].lower()
    else:
        first = segments[0].lower()

    # Special handling for common paths (extended to match more B2B SaaS site categories)
    if first in ("blog", "blogs", "article", "articles", "post", "posts"):
        return "Blog"
    elif first in (
        "doc",
        "docs",
        "documentation",
        "help",
        "guide",
        "guides",
        "developers",
        "developer",
    ):
        return "Docs"
    elif first in ("product", "products", "solution", "solutions"):
        return "Products"
    elif first in ("pricing", "price", "prices", "plan", "plans"):
        return "Pricing"
    elif first in ("about", "about-us", "company"):
        return "About"
    elif first in ("contact", "support", "help"):
        return "Support"
    elif first in ("case", "cases", "use-case", "use-cases"):
        return "Use Cases"
    elif first in ("integration", "integrations", "resource", "resources"):
        return "Integrations"
    elif first in ("location", "locations", "proxy-location", "proxy-locations"):
        return "Proxy Locations"
    elif first in ("legal", "privacy", "terms", "policy", "policies"):
        return "Legal"
    elif first in ("career", "careers", "jobs", "hiring"):
        return "Careers"
    elif first in ("press", "news", "newsroom", "media"):
        return "Press"
    elif first in ("affiliate", "affiliates", "partner", "partners"):
        return "Partners"
    elif first in ("dataset", "datasets", "data"):
        return "Datasets"
    elif first in ("serp", "search"):
        return "SERP"
    elif first in ("scraper", "scrapers", "scraping"):
        return "Scrapers"
    elif first in ("proxy", "proxies"):
        return "Proxies"

    # simple normalization: replace "-" with space and title-case
    name = first.replace("-", " ").strip().title()
    return name or "Other"


def _base_group_weight(group: str) -> int:
    """
    Heuristic weight for groups, used in scoring when no explicit priority is set.
    Enhanced to match B2B SaaS site prioritization.
    """
    key = group.lower()
    if key == "home":
        return 40
    if key in {"products", "product"}:
        return 35
    if key in {"pricing"}:
        return 30
    if key in {"docs", "documentation"}:
        return 28
    if key in {"proxies", "proxy"}:
        return 27
    if key in {"scrapers", "scraper", "scraping"}:
        return 26
    if key in {"blog", "blogs"}:
        return 25
    if key in {"serp"}:
        return 24
    if key in {"use cases", "usecases"}:
        return 24
    if key in {"integrations", "integration"}:
        return 24
    if key in {"datasets", "dataset"}:
        return 23
    if key in {"proxy locations", "locations"}:
        return 22
    if key in {"about", "about us"}:
        return 20
    if key in {"partners", "affiliates"}:
        return 19
    if key in {"legal"}:
        return 18
    if key in {"press", "news"}:
        return 17
    if key in {"careers"}:
        return 15
    return 10


def _compute_score(group: str, priority: int, path: str) -> int:
    """
    Compute a simple importance score based on group, priority and URL depth.
    Improved scoring: less penalty for depth, more weight on group and priority.
    """
    depth = max(len([seg for seg in path.split("/") if seg]) - 1, 0)
    base_score = _base_group_weight(group)

    # Priority weight is higher
    priority_weight = priority * 2 if priority > 0 else 0

    # Depth penalty reduced (from 3 to 2) to avoid over-penalizing deep pages
    depth_penalty = depth * 2

    score = base_score + priority_weight - depth_penalty

    # Bonus for homepage and root path
    if path == "/" or path == "":
        score += 10

    return max(0, min(200, score))  # Increased max score to 200


def _default_exclude_rules() -> List[FilterRule]:
    """
    Built-in common exclude rules to avoid including obvious noise pages
    (search, pagination, admin interfaces, etc.) in llms when user hasn't configured any excludes.
    """
    # 说明：
    # - 这些规则是「保守的默认降噪」，只处理非常常见且几乎总是噪声的 URL 形态
    # - 具体站点如果有特殊需求，仍然建议在配置文件里用 filters.exclude 做精细控制
    patterns = [
        r"/wp-admin/",
        r"/wp-json/",
        r"/search",
        r"[?&]s=",
        r"[?&]page=\d+",
        # 典型分页 URL（包括博客分页）：/page/2, /blog/page/3 等
        r"/page/\d+/?$",
        r"/tag/",
        r"/category/",
        r"/feed/?$",
        r"\.xml$",
        r"\.rss$",
        r"/404",
    ]
    return [FilterRule(pattern=p) for p in patterns]


def filter_and_group_urls(config: AppConfig, urls: List[str]) -> List[PageEntry]:
    include_rules = config.filters.include
    exclude_rules = list(config.filters.exclude)
    if config.filters.use_default_excludes:
        exclude_rules = _default_exclude_rules() + exclude_rules
    auto_group = config.filters.auto_group

    results: List[PageEntry] = []
    default_lang = (config.site.default_language or "en").lower()

    for u in urls:
        path = _relative_path(config.site.base_url, u)

        # If auto language filtering is enabled and path has language prefix that's not default language, skip
        if config.filters.auto_filter_languages:
            lang_prefix = _detect_language_prefix(path)
            if lang_prefix and lang_prefix != default_lang:
                continue

        # Exclude first - but if include rule matches, prioritize keeping it
        excluded = False
        if exclude_rules:
            # First check if any include rule matches
            has_include_match = any(_match_rule(path, r) for r in include_rules)
            # If include matches, exclude rules need to be stricter (exact path match)
            # If no include matches, use normal exclude rules
            if has_include_match:
                # For include matches, only exclude exact matching exclude rules
                excluded = any(
                    _match_rule(path, r)
                    and (r.pattern.startswith("^") and r.pattern.endswith("$"))
                    for r in exclude_rules
                )
            else:
                excluded = any(_match_rule(path, r) for r in exclude_rules)

        if excluded:
            continue

        # Include rules determine group/priority; if none match, optionally auto-group
        matched_rule: Optional[FilterRule] = None
        for r in include_rules:
            if _match_rule(path, r):
                matched_rule = r
                break

        if matched_rule:
            group = matched_rule.group if matched_rule.group else "Other"
            priority = matched_rule.priority
        else:
            # Improved auto-grouping: consider subdomain and path
            if auto_group:
                # Extract subdomain info from URL
                from urllib.parse import urlparse

                parsed = urlparse(u)
                host = parsed.netloc.lower()

                # If path is empty or only /, use domain info
                if path == "/" or not path.strip("/"):
                    if "blog" in host or "/blog" in path:
                        group = "Blog"
                    elif "doc" in host or "developer" in host or "developers" in host:
                        group = "Docs"
                    else:
                        group = "Home"
                else:
                    group = _auto_group_from_path(path)
            else:
                group = "Other"
            priority = 0

        score = _compute_score(group, priority, path)
        results.append(
            PageEntry(url=u, path=path, group=group, priority=priority, score=score)
        )

    # Sort by group then score (desc) then path
    results.sort(key=lambda p: (p.group, -p.score, p.path))
    return results
