"""
Subdomain discovery and URL collection enhancement
Automatically discover subdomains and collect URLs from all subdomains
"""

from __future__ import annotations

from typing import List, Set
from urllib.parse import urlparse
import requests

from .config import AppConfig, SourceConfig
from .logger import get_logger

logger = get_logger(__name__)


def discover_subdomains_from_sitemap(
    base_url: str, session: requests.Session
) -> Set[str]:
    """
    Automatically discover all subdomains from sitemap

    Args:
        base_url: Base URL, e.g. https://www.example.com
        session: requests session

    Returns:
        Set of discovered subdomains, e.g. {'www.example.com', 'docs.example.com', 'blog.example.com'}
    """
    discovered: Set[str] = set()

    # Extract main domain from base_url
    parsed = urlparse(base_url)
    main_domain = parsed.netloc.lower()

    # Extract root domain (e.g. thordata.com)
    parts = main_domain.split(".")
    if len(parts) >= 2:
        root_domain = ".".join(parts[-2:])  # Take last two parts
    else:
        root_domain = main_domain

    discovered.add(main_domain)  # Add main domain

    # Try to get sitemap
    sitemap_urls = [
        f"{parsed.scheme}://{main_domain}/sitemap.xml",
        f"{parsed.scheme}://{main_domain}/sitemap_index.xml",
    ]

    for sitemap_url in sitemap_urls:
        try:
            resp = session.get(sitemap_url, timeout=10)
            if resp.status_code == 200:
                # Parse sitemap, extract all URL domains
                from .sitemap import _parse_sitemap_xml, _expand_sitemap_index

                seen: Set[str] = set()
                urls = _parse_sitemap_xml(resp.text, source_url=sitemap_url)

                # If it's a sitemap index, expand it
                if any(u.endswith(".xml") for u in urls):
                    all_urls: List[str] = []
                    for u in urls:
                        if u.endswith(".xml"):
                            all_urls.extend(_expand_sitemap_index(u, session, seen))
                        else:
                            all_urls.append(u)
                    urls = all_urls

                # Extract domains from all URLs
                for url in urls:
                    try:
                        u_parsed = urlparse(url)
                        host = u_parsed.netloc.lower()
                        if host and root_domain in host:
                            discovered.add(host)
                    except Exception:
                        continue

                break  # Exit after successfully getting sitemap
        except Exception:
            continue

    return discovered


def discover_subdomains_comprehensive(
    base_url: str, session: requests.Session
) -> Set[str]:
    """
    Comprehensive subdomain discovery using multiple methods

    Methods:
    1. From sitemap.xml
    2. From robots.txt (Sitemap declarations)
    3. From crawling homepage links

    Args:
        base_url: Base URL
        session: requests session

    Returns:
        Set of all discovered subdomains
    """
    discovered: Set[str] = set()

    parsed = urlparse(base_url)
    main_domain = parsed.netloc.lower()
    scheme = parsed.scheme

    # Extract root domain
    parts = main_domain.split(".")
    if len(parts) >= 2:
        root_domain = ".".join(parts[-2:])
    else:
        root_domain = main_domain

    discovered.add(main_domain)

    # Method 1: From sitemap
    try:
        sitemap_subdomains = discover_subdomains_from_sitemap(base_url, session)
        discovered.update(sitemap_subdomains)
        logger.info(f"Discovered {len(sitemap_subdomains)} subdomains from sitemap")
    except Exception as e:
        logger.warning(f"Failed to discover subdomains from sitemap: {e}")

    # Method 2: From robots.txt
    try:
        robots_url = f"{scheme}://{main_domain}/robots.txt"
        resp = session.get(robots_url, timeout=10)
        if resp.status_code == 200:
            for line in resp.text.splitlines():
                line = line.strip()
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    try:
                        sitemap_parsed = urlparse(sitemap_url)
                        sitemap_host = sitemap_parsed.netloc.lower()
                        if sitemap_host and root_domain in sitemap_host:
                            discovered.add(sitemap_host)
                    except Exception:
                        continue
    except Exception as e:
        logger.debug(f"Could not read robots.txt: {e}")

    # Method 3: From homepage links (limited crawl)
    try:
        resp = session.get(base_url, timeout=10)
        if resp.status_code == 200:
            from html.parser import HTMLParser

            class LinkExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.links = set()

                def handle_starttag(self, tag, attrs):
                    if tag.lower() == "a":
                        for k, v in attrs:
                            if k.lower() == "href":
                                if v:
                                    self.links.add(v)

            parser = LinkExtractor()
            parser.feed(resp.text)

            for href in parser.links:
                try:
                    # Resolve relative URLs
                    from urllib.parse import urljoin

                    abs_url = urljoin(base_url, href)
                    u_parsed = urlparse(abs_url)
                    host = u_parsed.netloc.lower()
                    if host and root_domain in host and host not in discovered:
                        discovered.add(host)
                except Exception:
                    continue
    except Exception as e:
        logger.debug(f"Could not extract subdomains from homepage: {e}")

    return discovered


def enhance_sources_with_subdomains(
    config: AppConfig,
    session: requests.Session,
    selected_subdomains: Set[str] | None = None,
) -> List[SourceConfig]:
    """
    Enhance config sources by automatically adding discovered subdomains

    If selected_subdomains is provided, only use those subdomains.
    Otherwise, discover all subdomains automatically.

    Args:
        config: App configuration
        session: requests session
        selected_subdomains: Optional set of subdomains to use (if None, auto-discover)

    Returns:
        Enhanced list of source configurations
    """
    # Discover or use selected subdomains
    if selected_subdomains is not None:
        discovered = selected_subdomains
    else:
        discovered = discover_subdomains_comprehensive(config.site.base_url, session)

    # Check configured allowed_domains
    configured_domains = set(config.site.allowed_domains)

    # Merge discovered subdomains into allowed_domains
    all_domains = configured_domains | discovered
    config.site.allowed_domains = list(all_domains)

    # Check configured sources
    configured_sources = {
        src.url for src in config.sources if src.type in ("sitemap", "crawl")
    }

    # Add sitemap source for each discovered subdomain (if not already configured)
    enhanced_sources = list(config.sources)
    parsed = urlparse(config.site.base_url)
    scheme = parsed.scheme

    for domain in discovered:
        # Skip if already configured
        if any(domain in src.url for src in config.sources):
            continue

        # Try to add sitemap source
        sitemap_url = f"{scheme}://{domain}/sitemap.xml"
        if sitemap_url not in configured_sources:
            enhanced_sources.append(
                SourceConfig(
                    type="sitemap",
                    url=sitemap_url,
                    max_depth=2,
                    max_urls=0,
                    urls=[],
                )
            )

    return enhanced_sources
