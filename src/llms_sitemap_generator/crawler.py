from __future__ import annotations

import heapq
from collections import deque
from typing import List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urldefrag
import time

import requests
from html.parser import HTMLParser

from .logger import get_logger
from .url_utils import normalize_url, should_skip_by_extension, is_same_root_domain

logger = get_logger(__name__)


def _is_allowed_domain(url: str, allowed_hosts: Set[str]) -> bool:
    u = urlparse(url)
    host = (u.netloc or "").lower()
    return bool(host) and host in allowed_hosts


def _get_url_priority(url: str) -> int:
    """
    Calculate priority score for a URL. Higher score = higher priority.
    B2B SaaS sites: prioritize product, pricing, docs pages.
    """
    path = urlparse(url).path.lower()

    # High priority paths (B2B SaaS focus)
    high_priority = [
        "/products",
        "/pricing",
        "/docs",
        "/documentation",
        "/features",
        "/solutions",
        "/api",
        "/guides",
        "/blog",  # Moved blog to high priority to ensure all articles are collected
    ]
    for hp in high_priority:
        if hp in path:
            return 3

    # Medium priority paths
    medium_priority = [
        "/resources",
        "/case-studies",
        "/about",
        "/contact",
        "/help",
        "/faq",
        "/integrations",
    ]
    for mp in medium_priority:
        if mp in path:
            return 2

    # Low priority paths
    low_priority = [
        "/careers",
        "/jobs",
        "/press",
        "/news",
        "/legal",
        "/privacy",
        "/terms",
        "/cookies",
    ]
    for lp in low_priority:
        if lp in path:
            return 0

    # Default priority
    return 1


class _LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: Set[str] = set()

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = None
        # Check for class attribute to detect React/className noise
        has_classname_attr = False
        for k, v in attrs:
            if k.lower() == "href":
                href = v
            elif k.lower() == "class" and v:
                # Check if class contains "className" or other React-like patterns
                class_val = str(v).lower()
                if "classname" in class_val or "react" in class_val:
                    has_classname_attr = True
        
        if not href:
            return
        
        href_l = href.strip().lower()
        # 明显不是正常导航链接的 href 直接跳过
        if href_l.startswith(("javascript:", "mailto:", "tel:", "#")):
            return
        
        # 过滤掉明显错误/噪声的 href：
        # - 含有 React/前端 className 片段（在 href 中或 class 属性中）
        # - 纯邮箱样式但未以 mailto: 开头
        # - 包含 /className/ 路径（React 错误注入）
        # - 包含 /page/ 但路径看起来不正常（如 /className/page/2）
        if "classname" in href_l or has_classname_attr:
            return
        if "/className/" in href_l or "/classname/" in href_l:
            return
        # Filter out suspicious pagination URLs that contain className
        if "/page/" in href_l and ("classname" in href_l or "className" in href_l):
            return
        if "@" in href_l and not href_l.startswith(("http://", "https://")):
            # 很大概率是从 email 文本误解析出来的「链接」
            return
        
        # Additional validation: check if href looks like a valid URL path
        # Skip URLs that are clearly malformed (e.g., just "className" or similar)
        if href_l and not href_l.startswith(("http://", "https://", "/", "?")):
            # Relative URLs should start with / or ?
            if not href_l.startswith(("./", "../")):
                return
        
        self.links.add(href)


def crawl_site(
    start_url: str,
    *,
    allowed_hosts: Set[str],
    session: requests.Session,
    max_urls: int,
    max_depth: int = 2,
    root_domain: str | None = None,
    allow_same_root_subdomains: bool = False,
    polite: bool = True,
    request_delay_s: float = 0.25,
    max_retries: int = 4,
    failed_urls: Optional[List[dict]] = None,
) -> List[str]:
    """
    Very simple same-domain crawler for sites without sitemap.xml.
    - BFS from start_url up to max_depth
    - Only keeps URLs on the same domain
    - Limits total collected URLs to max_urls

    Args:
        failed_urls: Optional list to record failed URLs with error info.
                     Each entry will be a dict: {"url": str, "error": str, "status_code": int|None}
    """
    visited: Set[str] = set()
    results: List[str] = []

    # Default headers to reduce 429 risk a bit
    session.headers.setdefault(
        "User-Agent",
        "llms-sitemap-generator/0.1.0 (+https://github.com/thordata/llms-sitemap-generator)",
    )
    session.headers.setdefault(
        "Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    )

    start_url = normalize_url(urldefrag(start_url)[0])

    # Use priority queue: (priority, counter, url, depth)
    # Priority: lower number = higher priority (heapq is min-heap)
    # Counter ensures stable sorting for same-priority items
    counter = 0
    start_priority = _get_url_priority(start_url)
    queue: List[Tuple[int, int, str, int]] = []
    heapq.heappush(queue, (-start_priority, counter, start_url, 0))
    counter += 1

    logger.info(
        f"Starting crawl from {start_url} "
        f"(max_depth={max_depth}, max_urls={max_urls}, "
        f"allowed_hosts={len(allowed_hosts)}, polite={polite})"
    )

    # Dynamic allowed hosts set when auto-subdomain is enabled
    dynamic_allowed_hosts: Set[str] = set(h.lower() for h in allowed_hosts if h)

    iteration = 0
    while queue and len(results) < max_urls:
        _, _, current, depth = heapq.heappop(queue)

        # 定期报告进度
        iteration += 1
        if iteration % 10 == 0:
            logger.info(
                f"Crawl progress: visited={len(visited)}, "
                f"queued={len(queue)}, results={len(results)}, depth={depth}"
            )

        if current in visited:
            continue
        visited.add(current)

        current_parsed = urlparse(current)
        current_host = (current_parsed.netloc or "").lower()

        if not _is_allowed_domain(current, dynamic_allowed_hosts):
            # If enabled, allow same-root subdomains discovered during crawling
            if (
                allow_same_root_subdomains
                and root_domain
                and is_same_root_domain(current_host, root_domain)
            ):
                dynamic_allowed_hosts.add(current_host)
            else:
                continue

        # Skip obvious binary/static assets
        if should_skip_by_extension(current):
            continue

        # Polite crawling: delay + retry/backoff for 429/5xx
        last_err: Exception | None = None
        resp = None
        for attempt in range(max_retries + 1):
            try:
                if polite and request_delay_s > 0:
                    time.sleep(request_delay_s)
                resp = session.get(current, timeout=20)
                # 对 404 直接放弃，不做指数重试，避免在明显死链上浪费大量时间
                if resp.status_code == 404:
                    logger.warning(
                        f"404 Not Found for {current}; skipping retries "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    resp = None
                    break
                # Handle 429 with backoff / Retry-After
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    sleep_s = 2.0 * (2**attempt)
                    if retry_after:
                        try:
                            sleep_s = max(sleep_s, float(retry_after))
                        except Exception:
                            pass
                    logger.warning(
                        f"429 Too Many Requests for {current}; backing off {sleep_s:.1f}s (attempt {attempt + 1}/{max_retries + 1})"
                    )
                    time.sleep(sleep_s)
                    continue
                # Retry on transient 5xx
                if resp.status_code in {500, 502, 503, 504, 520}:
                    sleep_s = 1.5 * (2**attempt)
                    logger.warning(
                        f"{resp.status_code} for {current}; retrying in {sleep_s:.1f}s (attempt {attempt + 1}/{max_retries + 1})"
                    )
                    time.sleep(sleep_s)
                    continue
                resp.raise_for_status()
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                # final attempt falls through
                if attempt >= max_retries:
                    resp = None
                    break
                sleep_s = 1.0 * (2**attempt)
                logger.warning(
                    f"Fetch failed for {current}: {e}; retrying in {sleep_s:.1f}s (attempt {attempt + 1}/{max_retries + 1})"
                )
                time.sleep(sleep_s)

        if resp is None:
            logger.warning(f"Crawler failed to fetch {current}: {last_err}")
            # Record failed URL for later export/analysis
            if failed_urls is not None:
                status_code = None
                error_msg = str(last_err)
                # Try to extract status code from error message
                if "404" in error_msg:
                    status_code = 404
                elif "403" in error_msg:
                    status_code = 403
                elif "500" in error_msg:
                    status_code = 500
                elif "502" in error_msg:
                    status_code = 502
                elif "503" in error_msg:
                    status_code = 503
                failed_urls.append(
                    {
                        "url": current,
                        "error": error_msg,
                        "status_code": status_code,
                    }
                )
            continue

        # Only include HTML-ish pages in results (avoid PDFs etc.)
        content_type = (resp.headers.get("Content-Type") or "").lower()
        if (
            "text/html" in content_type
            or "application/xhtml+xml" in content_type
            or content_type == ""
        ):
            results.append(current)
        else:
            # Non-HTML content: don't parse and don't include as a page entry
            continue
        if depth >= max_depth:
            continue

        # Parse links
        parser = _LinkExtractor()
        try:
            parser.feed(resp.text)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Crawler failed to parse HTML at {current}: {e}")
            continue

        # 记录从当前页面提取的链接数
        logger.debug(f"Extracted {len(parser.links)} links from {current}")

        for href in parser.links:
            abs_url = urljoin(current, href)
            abs_url = normalize_url(urldefrag(abs_url)[0])
            if should_skip_by_extension(abs_url):
                continue

            # Update allowed hosts dynamically if subdomain discovery enabled
            host = (urlparse(abs_url).netloc or "").lower()
            if (
                allow_same_root_subdomains
                and root_domain
                and is_same_root_domain(host, root_domain)
            ):
                dynamic_allowed_hosts.add(host)

            if abs_url not in visited and _is_allowed_domain(
                abs_url, dynamic_allowed_hosts
            ):
                # Only add to queue if we haven't reached the limit yet
                # But allow processing existing queue items even after limit is reached
                if len(results) < max_urls:
                    # Calculate priority for the new URL
                    priority = _get_url_priority(abs_url)
                    heapq.heappush(queue, (-priority, counter, abs_url, depth + 1))
                    counter += 1

    # 爬取完成后的总结
    logger.info(
        f"Crawl completed: collected {len(results)} URLs from {start_url}, "
        f"visited {len(visited)} pages, max depth reached"
    )

    if len(results) >= max_urls:
        logger.info(f"Crawl stopped: reached max_urls limit ({max_urls})")
    elif not queue:
        logger.info("Crawl stopped: queue exhausted (all reachable pages visited)")

    return results
