"""Generator heal loop tests."""

import json
from pathlib import Path

from nina.generator.heal import (
    apply_heal_to_contract,
    failure_records,
    normalize_reports,
    prioritize_entries,
    suggest_selector_replacement,
)
from nina.generator.stages.dom_extract import extract_dom_signals
from nina.generator.stages.validate import validate_contract

EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "examples"


def test_normalize_reports_variants():
    single = {"siteId": "s", "contractVersion": "1.0.0", "pageUrl": "http://x/", "failures": []}
    assert len(normalize_reports(single)) == 1
    assert len(normalize_reports({"reports": [single]})) == 1
    assert len(normalize_reports([single])) == 1


def test_prioritize_entries_boosts_failed_urls():
    entries = [{"url": "https://example.com/", "priority": 0.3}]
    reports = [{
        "pageUrl": "https://example.com/cart",
        "failures": [{"actionId": "checkout", "stepIndex": 0, "op": "click", "reason": "not_found"}],
    }]
    merged = prioritize_entries(entries, reports)
    assert merged[0]["url"] == "https://example.com/cart"
    assert merged[0]["healTarget"] is True


def test_suggest_selector_for_search_fill():
    html = '<html><body><input type="search" id="new-q" name="query"></body></html>'
    signals = extract_dom_signals(html)
    replacement = suggest_selector_replacement(
        {
            "op": "fill",
            "actionId": "search",
            "selector": "#old-q",
            "reason": "not_found",
            "snapshot": {"visibleLabels": ["Search products"]},
        },
        signals,
    )
    assert replacement == "#new-q"


def test_apply_heal_patches_selector_id():
    contract = {
        "site": {"id": "test-site", "name": "T", "baseUrl": "https://example.com"},
        "version": "1.0.0",
        "pages": [{"id": "home", "urlPattern": "/"}],
        "actions": [{
            "id": "search",
            "description": "Search the site",
            "parameters": {"query": {"type": "string", "required": True}},
            "execute": {
                "type": "dom",
                "steps": [
                    {"op": "fill", "selectorId": "search_input", "param": "query"},
                    {"op": "click", "selectorId": "search_submit"},
                ],
            },
        }],
        "selectors": {"search_input": "#old-q", "search_submit": "#old-btn"},
        "embed": {"panel": "right", "apiBase": "/v1/query"},
    }
    html = (
        '<html><body>'
        '<input type="search" id="fresh-q" name="query">'
        '<button type="submit" id="fresh-go">Search</button>'
        '</body></html>'
    )
    pages = [{"url": "https://example.com/", "pageType": "home", "html": html}]
    reports = [{
        "siteId": "test-site",
        "contractVersion": "1.0.0",
        "pageUrl": "https://example.com/",
        "failures": [{
            "actionId": "search",
            "stepIndex": 0,
            "op": "fill",
            "selectorId": "search_input",
            "selector": "#old-q",
            "reason": "not_found",
        }],
    }]
    healed, log = apply_heal_to_contract(contract, reports, pages)
    assert healed["selectors"]["search_input"] == "#fresh-q"
    assert healed["version"] == "1.0.1"
    assert log[0]["status"] == "patched"
    ok, errors = validate_contract(healed)
    assert ok, errors


def test_failure_records_flattens():
    rows = failure_records([{
        "pageUrl": "https://example.com/cart",
        "failures": [{"actionId": "checkout", "stepIndex": 0, "op": "click", "reason": "not_found"}],
    }])
    assert len(rows) == 1
    assert rows[0]["pageUrl"] == "https://example.com/cart"


def test_heal_only_requires_existing_agent(tmp_path):
    from nina.generator.pipeline import run_heal_only

    (tmp_path / "nina.site.yaml").write_text(
        "site:\n  id: test-site\n  name: T\n  baseUrl: https://example.com\npublish:\n  outputDir: dist\n",
        encoding="utf-8",
    )
    reports = [{
        "siteId": "test-site",
        "contractVersion": "1.0.0",
        "pageUrl": "https://example.com/",
        "failures": [{
            "actionId": "search",
            "stepIndex": 0,
            "op": "fill",
            "reason": "not_found",
        }],
    }]
    result = run_heal_only(tmp_path, reports, dry_run=True)
    assert not result.ok
    assert any("agent.json" in err for err in result.errors)
