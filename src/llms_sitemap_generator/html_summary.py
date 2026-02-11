from __future__ import annotations

from html.parser import HTMLParser
from typing import List, Optional, Tuple

import re
import requests

from .logger import get_logger

logger = get_logger(__name__)


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.in_h1 = False
        self.in_h2 = False
        self.in_script = False
        self.in_style = False
        self.in_article = False
        self.in_main = False
        self.title: str = ""
        self.h1: str = ""
        self.h2: str = ""
        self.description: Optional[str] = None
        self.first_paragraph: Optional[str] = None
        self.paragraphs: List[str] = []
        self.in_paragraph = False
        self.current_paragraph = ""

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        if tag_lower == "title":
            self.in_title = True
        elif tag_lower == "h1":
            self.in_h1 = True
        elif tag_lower == "h2":
            self.in_h2 = True
        elif tag_lower == "script":
            self.in_script = True
        elif tag_lower == "style":
            self.in_style = True
        elif tag_lower in ("article", "main", "section"):
            # Track if we're in main content area
            if tag_lower == "article":
                self.in_article = True
            elif tag_lower == "main":
                self.in_main = True
        elif tag_lower == "meta":
            attr_dict = {k.lower(): v for k, v in attrs}
            name = (attr_dict.get("name") or "").lower()
            if name == "description" and not self.description:
                content = attr_dict.get("content")
                if isinstance(content, str) and len(content.strip()) > 10:
                    self.description = content.strip()
            # Also check for og:description
            prop = (attr_dict.get("property") or "").lower()
            if prop == "og:description" and not self.description:
                content = attr_dict.get("content")
                if isinstance(content, str) and len(content.strip()) > 10:
                    self.description = content.strip()
        elif tag_lower == "p":
            # Capture paragraphs, especially in article/main content
            self.in_paragraph = True
            self.current_paragraph = ""

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower == "title":
            self.in_title = False
        elif tag_lower == "h1":
            self.in_h1 = False
        elif tag_lower == "h2":
            self.in_h2 = False
        elif tag_lower == "script":
            self.in_script = False
        elif tag_lower == "style":
            self.in_style = False
        elif tag_lower in ("article", "main", "section"):
            if tag_lower == "article":
                self.in_article = False
            elif tag_lower == "main":
                self.in_main = False
        elif tag_lower == "p":
            self.in_paragraph = False
            if self.current_paragraph:
                text = self.current_paragraph.strip()
                # Only keep substantial paragraphs (at least 20 chars)
                if len(text) > 20:
                    self.paragraphs.append(text)
                    # Use first substantial paragraph as description if no meta description
                    if not self.description and not self.first_paragraph:
                        self.first_paragraph = text[:400]  # Limit length
                self.current_paragraph = ""

    def handle_data(self, data):
        if self.in_script or self.in_style:
            return
        if self.in_title:
            self.title += data
        elif self.in_h1 and len(self.h1) < 200:  # Limit h1 length
            self.h1 += data
        elif self.in_h2 and len(self.h2) < 200:  # Limit h2 length
            self.h2 += data
        elif self.in_paragraph:
            # Collect paragraph text
            self.current_paragraph += data


def fetch_basic_summary(url: str, session: requests.Session, site_name: Optional[str] = None) -> Tuple[str, str]:
    """
    Fetch a page and extract a simple title + description from HTML.
    This is the non-LLM fallback for generating llms.txt entries.
    """
    try:
        resp = session.get(url, timeout=20)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to fetch page {url}: {e}")
        return url, "No description available."

    # Try to pick a sensible encoding to avoid mojibake on UTF-8 pages
    encoding = resp.encoding
    if not encoding or encoding.lower() in {"iso-8859-1", "latin-1"}:
        encoding = resp.apparent_encoding or "utf-8"

    try:
        text = resp.content.decode(encoding, errors="ignore")
    except Exception:
        text = resp.text

    parser = _MetaParser()
    try:
        parser.feed(text)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Failed to parse HTML for {url}: {e}")

    # Use title, fallback to h1, fallback to h2, fallback to url
    raw_title = parser.title.strip() or parser.h1.strip() or parser.h2.strip() or url

    # Use description, fallback to first paragraph, fallback to first substantial paragraph
    desc = (parser.description or "").strip()
    if not desc and parser.first_paragraph:
        desc = parser.first_paragraph.strip()
    # If still no description, try to use first paragraph from main content
    if not desc and parser.paragraphs:
        for para in parser.paragraphs:
            if len(para) > 30:  # Prefer longer paragraphs
                desc = para[:400]  # Limit length
                break
        if not desc:
            desc = parser.paragraphs[0][:400] if parser.paragraphs else ""
    
    # If still no description, generate a meaningful one from title/URL
    if not desc or len(desc) < 10:
        # Extract site name from URL if not provided
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or ""
        # Extract site name from domain (e.g., www.example.com -> example)
        site_display_name = site_name
        if not site_display_name and domain:
            # Remove www. prefix and extract main domain name
            domain_parts = domain.replace("www.", "").split(".")
            if len(domain_parts) >= 2:
                site_display_name = domain_parts[0].title()  # Capitalize first letter
        
        # Try to generate description from title or URL path
        if raw_title and raw_title != url:
            # Use title as base for description
            if site_display_name:
                desc = f"Learn about {raw_title} at {site_display_name}. Find comprehensive information and resources."
            else:
                desc = f"Learn about {raw_title}. Find comprehensive information and resources."
        else:
            # Extract meaningful info from URL path
            path_parts = [p for p in parsed.path.split("/") if p and p not in ("", "www")]
            # Filter out common TLDs and domain parts
            filtered_parts = [p for p in path_parts if p not in ("com", "org", "net", "io", "co", "uk", "cn")]
            if filtered_parts:
                topic = " ".join(filtered_parts[-1].replace("-", " ").replace("_", " ").split())
                if site_display_name:
                    desc = f"Explore {topic} at {site_display_name}. Get detailed information and solutions."
                else:
                    desc = f"Explore {topic}. Get detailed information and solutions."
            else:
                if site_display_name:
                    desc = f"Visit {site_display_name} to learn more about our products and services."
                else:
                    desc = "Learn more about our products and services."

    # Normalize whitespace
    title = " ".join(raw_title.split())
    desc = " ".join(desc.split())
    
    # Ensure description is not too short or too long
    if len(desc) < 20:
        # If description is too short, try to enhance it
        if title and title != url:
            desc = f"{desc} {title}."
    if len(desc) > 500:
        desc = desc[:497] + "..."

    # Heuristic cleanup for 含站点名 / 导航噪声的标题（例如 GitBook）
    # 1）优先按常见分隔符截断，保留主标题部分
    for sep in [" | ", " - ", " — ", " · "]:
        if sep in title:
            candidate = title.split(sep)[0].strip()
            if 5 <= len(candidate) <= 120:
                title = candidate
                break

    # 2）进一步去掉明显的图标/控制字符噪声
    if len(title) > 80:
        title = re.sub(
            r"(chevron-|circle-|arrow-|sun-bright|desktop|moon|gitbook|xmark|barssearch)",
            "",
            title,
            flags=re.I,
        )
        title = re.sub(r"[|]{2,}", "|", title)
        title = " ".join(title.split())

    return title, desc
