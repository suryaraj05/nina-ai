"""Parse sitemap.xml into crawl URL list."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def parse_sitemap(path: Path, base_url: str | None = None) -> list[dict[str, Any]]:
    """
    Parse sitemap.xml (or sitemap index) into [{ url, priority, changefreq }].
    """
    tree = ET.parse(path)
    root = tree.getroot()
    root_tag = _strip_ns(root.tag)

    if root_tag == "sitemapindex":
        urls: list[dict[str, Any]] = []
        for sm in root:
            if _strip_ns(sm.tag) != "sitemap":
                continue
            loc = sm.find("sm:loc", _NS) or sm.find("loc")
            if loc is not None and loc.text:
                child = Path(loc.text.strip())
                if child.name.endswith(".xml"):
                    urls.extend(parse_sitemap(child, base_url))
        return urls

    entries: list[dict[str, Any]] = []
    for url_el in root:
        if _strip_ns(url_el.tag) != "url":
            continue
        loc_el = (
            url_el.find("sm:loc", _NS)
            or url_el.find(f"{{{_NS['sm']}}}loc")
            or url_el.find("loc")
        )
        loc_text = loc_el.text if loc_el is not None else url_el.findtext(f".//{{{_NS['sm']}}}loc")
        if not loc_text:
            continue
        url = loc_text.strip()
        if base_url:
            parsed_base = urlparse(base_url)
            parsed_url = urlparse(url)
            if parsed_url.netloc and parsed_url.netloc != parsed_base.netloc:
                continue
        priority = 0.5
        changefreq = "weekly"
        pri_el = url_el.find("sm:priority", _NS) or url_el.find("priority")
        cf_el = url_el.find("sm:changefreq", _NS) or url_el.find("changefreq")
        if pri_el is not None and pri_el.text:
            try:
                priority = float(pri_el.text)
            except ValueError:
                pass
        if cf_el is not None and cf_el.text:
            changefreq = cf_el.text.strip()
        entries.append({"url": url, "priority": priority, "changefreq": changefreq})

    entries.sort(key=lambda e: -e["priority"])
    return entries


def infer_page_type(url: str) -> str:
    """Heuristic page template id from URL path."""
    path = urlparse(url).path.lower().rstrip("/") or "/"
    rules = [
        (r"^/$", "home"),
        (r"/(cart|bag)", "cart"),
        (r"/(checkout|payment)", "checkout"),
        (r"/(login|signin|sign-in)", "login"),
        (r"/(account|profile|my-account)", "account"),
        (r"/(product|item|p)/", "product_detail"),
        (r"/(shop|catalog|collection|category|new-arrivals)", "product_list"),
        (r"/(search)", "search"),
        (r"/(contact)", "contact"),
    ]
    for pattern, page_id in rules:
        if re.search(pattern, path):
            return page_id
    return "generic"
