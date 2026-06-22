"""Executable contract validation tests."""

from nina.contract_validate import validate_executable


API_FIRST = {
    "site": {"id": "test-site", "name": "T", "baseUrl": "http://127.0.0.1:8000"},
    "version": "1.0.0",
    "pages": [{"id": "home", "urlPattern": "/*"}],
    "embed": {"panel": "right"},
    "apis": {"default": {"baseUrl": "http://127.0.0.1:8000"}},
    "actions": [
        {
            "id": "search",
            "description": "Search the site via API endpoint",
            "parameters": {"query": {"type": "string", "required": True}},
            "availableOn": ["home"],
            "execute": {
                "type": "api",
                "runtime": "server",
                "apiRef": {"method": "POST", "path": "/api/search"},
            },
        }
    ],
}

DOM_ONLY_BROKEN = {
    "site": {"id": "test-site", "name": "T", "baseUrl": "http://127.0.0.1:8000"},
    "version": "1.0.0",
    "pages": [{"id": "home", "urlPattern": "/*"}],
    "embed": {"panel": "right"},
    "selectors": {},
    "actions": [
        {
            "id": "click_thing",
            "description": "Click a button on the page",
            "parameters": {},
            "availableOn": ["home"],
            "execute": {
                "type": "dom",
                "steps": [{"op": "click", "selectorId": "missing_btn"}],
            },
        }
    ],
}


def test_api_first_passes_executable():
    ok, errors, _warnings = validate_executable(API_FIRST, strict=True)
    assert ok
    assert not errors


def test_dom_only_missing_selector_fails_strict():
    ok, errors, _warnings = validate_executable(DOM_ONLY_BROKEN, strict=True)
    assert not ok
    assert any("click_thing" in e for e in errors)
