from __future__ import annotations

from typing import List, Set
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests

from .config import AppConfig, SourceConfig
from .crawler import crawl_site
from .subdomain_discovery import enhance_sources_with_subdomains
from .logger import get_logger
from .url_utils import normalize_url, root_domain_from_host

logger = get_logger(__name__)


def _discover_sitemaps_from_robots(
    base_url: str, session: requests.Session
) -> List[str]:
    """
    Discover sitemap URLs from robots.txt.
    Many sites without /sitemap.xml still declare their sitemaps in robots.txt.
    """
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        return []
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        resp = session.get(robots_url, timeout=10)
        if resp.status_code != 200:
            return []
        text = resp.text or ""
    except Exception:  # noqa: BLE001
        return []

    sitemaps: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("sitemap:"):
            sm = line.split(":", 1)[1].strip()
            if sm:
                sitemaps.append(sm)

    # Normalize & de-dup
    out: List[str] = []
    seen: Set[str] = set()
    for sm in sitemaps:
        n = normalize_url(
            sm, prefer_https=True, drop_fragment=True, strip_trailing_slash=False
        )
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _is_allowed_domain(config: AppConfig, url: str) -> bool:
    u = urlparse(url)
    host = (u.netloc or "").lower()
    if not host:
        return False
    return host in config.site.allowed_domains


def _fetch_xml(url: str, session: requests.Session) -> str:
    resp = session.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text


def _parse_sitemap_xml(xml_text: str, source_url: str = "") -> List[str]:
    """Parse sitemap XML and extract URLs.

    Args:
        xml_text: The XML content to parse
        source_url: Optional source URL for error reporting

    Returns:
        List of extracted URLs
    """
    urls: List[str] = []
    try:
        root = ET.fromstring(xml_text)
        tag = root.tag.lower()

        if tag.endswith("urlset"):
            for url_el in root.findall(".//{*}url/{*}loc"):
                if url_el.text:
                    urls.append(url_el.text.strip())
        elif tag.endswith("sitemapindex"):
            for sm_el in root.findall(".//{*}sitemap/{*}loc"):
                if sm_el.text:
                    urls.append(sm_el.text.strip())
    except ET.ParseError as e:
        source_info = f" from {source_url}" if source_url else ""
        logger.warning(f"Failed to parse sitemap XML{source_info}: {e}")
        logger.debug(f"XML content preview (first 500 chars): {xml_text[:500]}")
    except Exception as e:
        source_info = f" from {source_url}" if source_url else ""
        logger.warning(f"Unexpected error parsing sitemap{source_info}: {e}")
    return urls


def _expand_sitemap_index(
    url: str, session: requests.Session, seen: Set[str]
) -> List[str]:
    if url in seen:
        return []
    seen.add(url)

    xml_text = _fetch_xml(url, session)
    candidates = _parse_sitemap_xml(xml_text, source_url=url)
    urls: List[str] = []
    for c in candidates:
        if c.endswith(".xml"):
            urls.extend(_expand_sitemap_index(c, session, seen))
        else:
            urls.append(c)
    return urls


def collect_urls_from_sources(
    config: AppConfig,
    session: requests.Session,
    progress_callback=None,
    failed_urls: list | None = None,
) -> List[str]:
    """
    Collect URLs from configured sources.

    Supported source types:
    - `type: sitemap`: Recursively collect URLs from sitemap.xml / sitemap index
    - `type: crawl`: Crawl same-domain URLs from specified entry URL (limited by max_depth / max_urls)
    - `type: static`: Import manually maintained URL list

    Args:
        config: Application configuration
        session: requests session
        progress_callback: Optional callback function(current_operation, url_count) for progress updates
    """
    # Make requests slightly more bot-friendly by default
    session.headers.setdefault(
        "User-Agent",
        "llms-sitemap-generator/0.1.0 (+https://github.com/thordata/llms-sitemap-generator)",
    )
    session.headers.setdefault(
        "Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    )

    # Configure connection pooling for better performance
    if not hasattr(session, "_adapter_configured"):
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=retry_strategy,
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session._adapter_configured = True

    collected: List[str] = []
    seen: Set[str] = set()

    # Optional enhancement: If auto subdomain discovery is enabled (typically by GUI),
    # automatically discover and add subdomain sources based on sitemap
    selected_subdomains = getattr(config, "selected_subdomains", None)
    if getattr(config, "enable_auto_subdomains", False):
        try:
            if progress_callback:
                progress_callback("Discovering subdomains...", len(collected))
            logger.info("Auto-discovering subdomains...")
            from .subdomain_discovery import enhance_sources_with_subdomains

            enhanced_sources = enhance_sources_with_subdomains(
                config, session, selected_subdomains
            )
            if len(enhanced_sources) > len(config.sources):
                logger.info(
                    f"Discovered {len(enhanced_sources) - len(config.sources)} additional subdomain sources"
                )
            config.sources = enhanced_sources
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"Auto subdomain discovery failed, continue with original sources: {e}"
            )
            # Ensure we can continue with original sources even if discovery fails

    if not config.sources:
        logger.warning(
            "No data sources configured. Please add at least one sitemap, crawl, or static source."
        )
        return []

    # Crawl can expand to same-root subdomains when enabled (e.g. developers.example.com)
    primary_host = urlparse(config.site.base_url).netloc.lower()
    root_domain = root_domain_from_host(primary_host)

    total_sources = len(config.sources)
    global_max = config.filters.max_urls
    for idx, src in enumerate(config.sources, 1):
        if progress_callback:
            progress_callback(
                f"Processing source {idx}/{total_sources}: {src.type} from {src.url}",
                len(collected),
            )

        # 如果已经达到全局 URL 上限，则提前停止后续数据源处理
        if len(collected) >= global_max:
            logger.info(
                f"Global max_urls={global_max} reached while processing sources; "
                "skipping remaining sources."
            )
            break

        if src.type == "sitemap":
            urls = _collect_from_sitemap_source(src, config, session, seen)
            if urls:
                logger.info(f"Collected {len(urls)} URLs from sitemap: {src.url}")
                if progress_callback:
                    progress_callback(
                        f"Collected {len(urls)} URLs from sitemap",
                        len(collected) + len(urls),
                    )
            collected.extend(urls)
        elif src.type == "crawl":
            # 为 crawl 源设置「剩余额度」：即使单源 max_urls 很大，也不能超过全局剩余预算
            per_source_max = src.max_urls or config.filters.max_urls
            remaining_budget = max(global_max - len(collected), 0)
            if remaining_budget <= 0:
                logger.info(
                    "Global crawl budget exhausted before this source; "
                    f"skipping crawl for {src.url}"
                )
                continue
            if per_source_max > remaining_budget:
                logger.info(
                    f"Adjusting crawl max_urls for {src.url} from {per_source_max} "
                    f"down to remaining budget {remaining_budget}"
                )
                per_source_max = remaining_budget
            logger.info(
                f"Crawling site from {src.url} "
                f"(max_depth={src.max_depth}, max_urls={per_source_max})"
            )
            if progress_callback:
                progress_callback(f"Crawling {src.url}...", len(collected))
            urls = crawl_site(
                src.url,
                allowed_hosts=set(config.site.allowed_domains),
                session=session,
                max_urls=per_source_max,
                max_depth=src.max_depth,
                root_domain=root_domain,
                allow_same_root_subdomains=bool(
                    getattr(config, "enable_auto_subdomains", False)
                ),
                polite=bool(getattr(config, "polite_crawl", True)),
                failed_urls=failed_urls,
            )
            if urls:
                logger.info(f"Collected {len(urls)} URLs from crawling: {src.url}")
                if progress_callback:
                    progress_callback(
                        f"Collected {len(urls)} URLs from crawling",
                        len(collected) + len(urls),
                    )
            collected.extend(urls)
        elif src.type == "static":
            urls = src.urls
            if not urls and src.url:
                urls = [src.url]
            if urls:
                logger.info(f"Collected {len(urls)} static URLs")
                if progress_callback:
                    progress_callback(
                        f"Collected {len(urls)} static URLs", len(collected) + len(urls)
                    )
            collected.extend(urls)

    # If sitemap sources yielded nothing, try robots.txt sitemap discovery as a fallback.
    # This helps for many frameworks (Next.js, etc.) that declare sitemaps in robots.txt.
    has_sitemap_source = any(s.type == "sitemap" for s in config.sources)
    if has_sitemap_source and not any(u for u in collected):
        discovered = _discover_sitemaps_from_robots(config.site.base_url, session)
        if discovered:
            logger.info(f"Discovered {len(discovered)} sitemap URL(s) from robots.txt")
            for sm in discovered:
                # avoid adding duplicates
                if any(
                    (
                        s.type == "sitemap"
                        and (s.url or "").rstrip("/") == sm.rstrip("/")
                    )
                    for s in config.sources
                ):
                    continue
                urls = _collect_from_sitemap_source(
                    SourceConfig(type="sitemap", url=sm), config, session, seen
                )
                if urls:
                    logger.info(f"Collected {len(urls)} URLs from robots sitemap: {sm}")
                collected.extend(urls)

    # De-duplicate and enforce same-site + global max_urls
    # Key fix: URL deduplication must handle trailing slash variations
    unique: List[str] = []
    normalized_seen: Set[str] = set()
    global_max = config.filters.max_urls
    for u in collected:
        if not _is_allowed_domain(config, u):
            continue
        # Canonicalize:
        # - force https
        # - drop fragment
        # - strip trailing slash
        normalized = normalize_url(
            u, prefer_https=True, drop_fragment=True, strip_trailing_slash=True
        )
        if normalized not in normalized_seen:
            normalized_seen.add(normalized)
            unique.append(
                normalized
            )  # Keep canonical format (prevents http/https duplicates)
        if len(unique) >= global_max:
            logger.info(f"Reached global max_urls={global_max}, truncating URL list.")
            break

    removed = len(collected) - len(unique)
    if removed > 0:
        logger.info(
            f"URL deduplication: {len(collected)} -> {len(unique)} URLs (removed {removed} duplicates)"
        )
    return unique


def _collect_from_sitemap_source(
    src: SourceConfig, config: AppConfig, session: requests.Session, seen: Set[str]
) -> List[str]:
    try:
        xml_text = _fetch_xml(src.url, session)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to fetch sitemap {src.url}: {e}")
        return []

    urls = _parse_sitemap_xml(xml_text, source_url=src.url)
    # If result looks like sitemap index, expand recursively
    if any(u.endswith(".xml") for u in urls):
        all_urls: List[str] = []
        for u in urls:
            if u.endswith(".xml"):
                all_urls.extend(_expand_sitemap_index(u, session, seen))
            else:
                all_urls.append(u)
        return all_urls

    return urls


def write_sitemap_xml(config: AppConfig, urls: List[str], path: str) -> None:
    """
    Write a basic sitemap.xml:
    - loc: Use filtered final URL list
    - lastmod / changefreq / priority are not enforced for now, keeping it simple and generic.
      Will be enhanced in future versions when reliable data sources are available.
    """
    urlset = ET.Element(
        "urlset", attrib={"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    )

    for u in urls:
        url_el = ET.SubElement(urlset, "url")
        loc_el = ET.SubElement(url_el, "loc")
        loc_el.text = u

    tree = ET.ElementTree(urlset)
    # Use utf-8 + XML declaration for compatibility with major search engines
    tree.write(path, encoding="utf-8", xml_declaration=True)
    logger.info(f"Wrote sitemap.xml to {path}")
