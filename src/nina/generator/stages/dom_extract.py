"""Extract stable DOM anchors from crawled HTML."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.search_inputs: list[dict[str, str]] = []
        self.buttons: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.forms: list[dict[str, str]] = []
        self._stack: list[str] = []
        self._text_parts: list[str] = []
        self._capture_text = False

    def handle_data(self, data: str) -> None:
        if self._capture_text and data.strip():
            self._text_parts.append(data.strip())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._stack.append(tag)
        attr = {k: (v or "") for k, v in attrs}
        if tag == "button":
            self._text_parts = []
            self._capture_text = True
        if tag == "input":
            itype = attr.get("type", "text").lower()
            if itype in ("search", "text") or "search" in attr.get("name", "").lower():
                sel = _selector_for(tag, attr)
                if sel:
                    self.search_inputs.append({"selector": sel, "name": attr.get("name", "")})
        elif tag == "button":
            sel = _selector_for(tag, attr)
            if sel:
                self.buttons.append({
                    "selector": sel,
                    "label": attr.get("aria-label", ""),
                    "text": "",
                })
        elif tag == "a" and attr.get("href"):
            sel = _selector_for(tag, attr)
            if sel:
                self.links.append({"selector": sel, "href": attr.get("href", "")})
        elif tag == "form":
            sel = _selector_for(tag, attr)
            if sel:
                self.forms.append({"selector": sel, "action": attr.get("action", "")})

    def handle_endtag(self, tag: str) -> None:
        if tag == "button" and self.buttons:
            self.buttons[-1]["text"] = " ".join(self._text_parts).strip()
            self._text_parts = []
            self._capture_text = False
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()


def _selector_for(tag: str, attr: dict[str, str]) -> str | None:
    if attr.get("data-testid"):
        return f'[data-testid="{attr["data-testid"]}"]'
    if attr.get("id"):
        return f"#{attr['id']}"
    if attr.get("name"):
        return f'{tag}[name="{attr["name"]}"]'
    if attr.get("aria-label"):
        return f'{tag}[aria-label="{attr["aria-label"]}"]'
    return None


def extract_dom_signals(html: str) -> dict[str, Any]:
    """Return search inputs, buttons, forms found in HTML."""
    parser = _AnchorParser()
    try:
        parser.feed(html or "")
    except Exception:
        pass
    return {
        "searchInputs": parser.search_inputs[:5],
        "buttons": parser.buttons[:10],
        "forms": parser.forms[:5],
        "links": parser.links[:20],
    }


def page_signals_from_crawl(pages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate DOM signals keyed by pageType."""
    by_type: dict[str, dict[str, Any]] = {}
    for page in pages:
        ptype = page.get("pageType", "generic")
        signals = extract_dom_signals(page.get("html", ""))
        if ptype not in by_type:
            by_type[ptype] = signals
        else:
            for key in ("searchInputs", "buttons", "forms"):
                existing = by_type[ptype].setdefault(key, [])
                for item in signals.get(key, []):
                    if item not in existing:
                        existing.append(item)
    return by_type
