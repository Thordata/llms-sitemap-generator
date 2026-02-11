from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse


_SKIP_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".zip",
    ".rar",
    ".7z",
    ".gz",
    ".tgz",
    ".mp4",
    ".mov",
    ".avi",
    ".mp3",
    ".wav",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}


def root_domain_from_host(host: str) -> str:
    """
    Best-effort root domain extraction.
    Note: This is a heuristic (no public suffix list). Good enough for most SaaS domains.
    """
    host = (host or "").lower().strip(".")
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def normalize_url(
    url: str,
    *,
    prefer_https: bool = True,
    drop_fragment: bool = True,
    strip_trailing_slash: bool = True,
) -> str:
    """
    Normalize URL for canonicalization/dedup:
    - lower-case host
    - (optionally) force https for http/https URLs
    - (optionally) drop fragment (#...)
    - (optionally) strip trailing slash (except for root '/')
    """
    parsed = urlparse(url.strip())
    scheme = parsed.scheme or "https"
    if prefer_https and scheme in {"http", "https"}:
        scheme = "https"
    netloc = (parsed.netloc or "").lower()
    path = parsed.path or "/"
    if strip_trailing_slash and path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    fragment = "" if drop_fragment else (parsed.fragment or "")
    rebuilt = urlunparse((scheme, netloc, path, parsed.params or "", parsed.query or "", fragment))
    return rebuilt


def should_skip_by_extension(url: str) -> bool:
    path = urlparse(url).path.lower()
    for ext in _SKIP_EXTENSIONS:
        if path.endswith(ext):
            return True
    return False


def is_same_root_domain(host: str, root_domain: str) -> bool:
    host = (host or "").lower()
    root_domain = (root_domain or "").lower()
    return bool(host) and bool(root_domain) and (host == root_domain or host.endswith("." + root_domain))

