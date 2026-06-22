"""Optional Playwright headless DOM extraction for generator pipeline."""

from __future__ import annotations

from typing import Any

from nina.generator.stages.dom_extract import extract_dom_signals


def _playwright_available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401

        return True
    except ImportError:
        return False


def extract_dom_signals_live(url: str, *, timeout_ms: int = 15000) -> dict[str, Any]:
    """
    Load a URL in headless Chromium and extract interactive anchors.
    Falls back to empty signals when Playwright is not installed.
    """
    if not _playwright_available():
        return {
            "searchInputs": [],
            "buttons": [],
            "forms": [],
            "links": [],
            "source": "playwright-unavailable",
        }

    from playwright.sync_api import sync_playwright

    html = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(min(500, timeout_ms // 4))
        html = page.content()
        browser.close()

    signals = extract_dom_signals(html)
    signals["source"] = "playwright"
    return signals


def enrich_crawl_with_playwright(
    pages: list[dict[str, Any]],
    *,
    timeout_ms: int = 15000,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    """Re-extract DOM signals for crawled pages using Playwright when available."""
    if not _playwright_available():
        return pages

    limit = max_pages or len(pages)
    out: list[dict[str, Any]] = []
    for idx, page in enumerate(pages):
        row = dict(page)
        if idx < limit and page.get("url"):
            live = extract_dom_signals_live(page["url"], timeout_ms=timeout_ms)
            row["domSignals"] = live
            if live.get("searchInputs") or live.get("buttons"):
                row["html"] = row.get("html") or ""
        out.append(row)
    return out
