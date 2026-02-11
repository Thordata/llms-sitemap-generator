"""
智能配置推荐模块
自动分析站点结构并推荐最佳配置
"""

from __future__ import annotations

from typing import List, Dict, Set, Optional
from urllib.parse import urlparse, urljoin
import requests

from .logger import get_logger
from .sitemap import _fetch_xml, _parse_sitemap_xml

logger = get_logger(__name__)


class SiteAnalyzer:
    """Analyze website structure and recommend optimal configuration"""

    def __init__(self, base_url: str, session: Optional[requests.Session] = None):
        self.base_url = base_url.rstrip("/")
        self.parsed = urlparse(self.base_url)
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent",
            "llms-sitemap-generator/0.1.0 (+https://github.com/thordata/llms-sitemap-generator)",
        )

        # Analysis results
        self.has_sitemap = False
        self.sitemap_urls: List[str] = []
        self.detected_sections: Dict[str, List[str]] = {}
        self.subdomains: Set[str] = set()
        self.estimated_page_count = 0

    def analyze(self) -> Dict:
        """
        Perform comprehensive site analysis
        Returns recommended configuration dict
        """
        logger.info(f"Starting site analysis for {self.base_url}")

        # Check for sitemap
        self._check_sitemap()

        # Detect common sections
        self._detect_sections()

        # Discover subdomains
        self._discover_subdomains()

        # Generate recommendations
        recommendations = self._generate_recommendations()

        logger.info(f"Site analysis complete for {self.base_url}")
        return recommendations

    def _check_sitemap(self):
        """Check if site has sitemap.xml"""
        sitemap_candidates = [
            f"{self.base_url}/sitemap.xml",
            f"{self.base_url}/sitemap_index.xml",
        ]

        for url in sitemap_candidates:
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    self.has_sitemap = True
                    self.sitemap_urls.append(url)
                    urls = _parse_sitemap_xml(resp.text, source_url=url)
                    self.estimated_page_count = len(urls)
                    logger.info(f"Found sitemap at {url} with {len(urls)} URLs")
                    break
            except Exception as e:
                logger.debug(f"Failed to check sitemap {url}: {e}")

    def _detect_sections(self):
        """Detect common website sections by checking common paths"""
        common_sections = {
            "blog": ["/blog", "/news", "/articles"],
            "docs": ["/docs", "/documentation", "/help", "/guide", "/api"],
            "products": ["/products", "/product", "/solutions", "/features"],
            "pricing": ["/pricing", "/plans", "/pricing-plans"],
            "about": ["/about", "/about-us", "/company"],
            "contact": ["/contact", "/support", "/help"],
            "legal": ["/legal", "/privacy", "/terms", "/cookies"],
            "careers": ["/careers", "/jobs", "/hiring", "/work-with-us"],
        }

        for section_name, paths in common_sections.items():
            found_urls = []
            for path in paths:
                url = urljoin(self.base_url, path)
                try:
                    resp = self.session.head(url, timeout=5, allow_redirects=True)
                    if resp.status_code == 200:
                        found_urls.append(url)
                        break  # Found one for this section
                except Exception:
                    pass

            if found_urls:
                self.detected_sections[section_name] = found_urls
                logger.info(f"Detected section '{section_name}' at {found_urls[0]}")

    def _discover_subdomains(self):
        """Discover subdomains from sitemap if available"""
        if not self.sitemap_urls:
            return

        try:
            from .subdomain_discovery import discover_subdomains_from_sitemap

            self.subdomains = discover_subdomains_from_sitemap(
                self.base_url, self.session
            )
            if self.subdomains:
                logger.info(
                    f"Discovered {len(self.subdomains)} subdomains: {self.subdomains}"
                )
        except Exception as e:
            logger.debug(f"Subdomain discovery failed: {e}")

    def _generate_recommendations(self) -> Dict:
        """Generate configuration recommendations based on analysis"""
        recommendations = {
            "site": {
                "base_url": self.base_url,
                "default_language": "en",
                "allowed_domains": [self.parsed.netloc],
            },
            "sources": [],
            "filters": {
                "auto_filter_languages": True,
                "auto_group": True,
                "use_default_excludes": True,
            },
            "analysis": {
                "has_sitemap": self.has_sitemap,
                "sitemap_urls": self.sitemap_urls,
                "detected_sections": list(self.detected_sections.keys()),
                "subdomains": list(self.subdomains),
                "estimated_pages": self.estimated_page_count,
            },
        }

        # Build sources
        sources = []

        # Add sitemap sources
        if self.sitemap_urls:
            for sitemap_url in self.sitemap_urls:
                sources.append(
                    {
                        "type": "sitemap",
                        "url": sitemap_url,
                    }
                )

        # Add crawl sources for detected sections
        for section_name, urls in self.detected_sections.items():
            if urls:
                # Calculate appropriate max_depth based on section type
                if section_name == "docs":
                    max_depth = 5  # Docs often have deep nesting
                    max_urls = 1000
                elif section_name == "blog":
                    max_depth = 3
                    max_urls = 500
                else:
                    max_depth = 2
                    max_urls = 200

                sources.append(
                    {
                        "type": "crawl",
                        "url": urls[0],
                        "max_depth": max_depth,
                        "max_urls": max_urls,
                    }
                )

        # Always add base crawl if no sitemap
        if not self.sitemap_urls:
            sources.append(
                {
                    "type": "crawl",
                    "url": self.base_url,
                    "max_depth": 3,
                    "max_urls": 1000,
                }
            )

        recommendations["sources"] = sources

        # Add subdomain sources
        for subdomain in self.subdomains:
            if subdomain != self.parsed.netloc:
                recommendations["site"]["allowed_domains"].append(subdomain)
                subdomain_sitemap = f"https://{subdomain}/sitemap.xml"
                sources.append(
                    {
                        "type": "sitemap",
                        "url": subdomain_sitemap,
                    }
                )

        # Generate include rules based on detected sections
        include_rules = []
        for section_name in self.detected_sections.keys():
            if section_name == "products":
                include_rules.append(
                    {
                        "pattern": f"^/{section_name}",
                        "group": "Products",
                        "priority": 150,
                    }
                )
            elif section_name == "docs":
                include_rules.append(
                    {
                        "pattern": f"^/{section_name}",
                        "group": "Docs",
                        "priority": 120,
                    }
                )
            elif section_name == "pricing":
                include_rules.append(
                    {
                        "pattern": f"^/{section_name}",
                        "group": "Pricing",
                        "priority": 130,
                    }
                )
            elif section_name == "blog":
                include_rules.append(
                    {
                        "pattern": f"^/{section_name}",
                        "group": "Blog",
                        "priority": 100,
                    }
                )

        if include_rules:
            recommendations["filters"]["include"] = include_rules

        return recommendations

    def print_report(self):
        """Print analysis report to console"""
        print("\n" + "=" * 60)
        print(f"Site Analysis Report: {self.base_url}")
        print("=" * 60)

        print(f"\n[Sitemap Status]")
        print(f"   Has sitemap: {self.has_sitemap}")
        if self.sitemap_urls:
            for url in self.sitemap_urls:
                print(f"   - {url}")
            print(f"   Estimated pages: {self.estimated_page_count}")

        print(f"\n[Detected Sections]")
        for section, urls in self.detected_sections.items():
            print(f"   [OK] {section}: {urls[0]}")

        if self.subdomains:
            print(f"\n[Subdomains ({len(self.subdomains)})]")
            for subdomain in sorted(self.subdomains):
                print(f"   - {subdomain}")

        print("\n" + "=" * 60)


def recommend_config(base_url: str, session: Optional[requests.Session] = None) -> Dict:
    """
    Quick helper function to get configuration recommendations

    Args:
        base_url: The base URL of the site to analyze
        session: Optional requests session

    Returns:
        Dictionary with recommended configuration
    """
    analyzer = SiteAnalyzer(base_url, session)
    recommendations = analyzer.analyze()
    analyzer.print_report()
    return recommendations
