"""API instruction expansion tests."""

from nina.contract import expand_api_instruction, expand_execute_steps


CONTRACT = {
    "site": {"id": "t", "name": "T", "baseUrl": "https://example.com"},
    "apis": {"default": {"baseUrl": "https://api.example.com"}},
    "actions": [
        {
            "id": "search",
            "description": "Search products",
            "parameters": {"query": {"type": "string", "required": True}},
            "execute": {
                "type": "api",
                "runtime": "browser",
                "apiRef": {
                    "apiId": "default",
                    "method": "POST",
                    "path": "/v1/search",
                    "bodyTemplate": {"q": "{query}"},
                    "paramMap": {"limit": "query"},
                },
            },
        },
        {
            "id": "section",
            "description": "Get section",
            "parameters": {"section": {"type": "string", "required": True}},
            "execute": {
                "type": "api",
                "runtime": "browser",
                "apiRef": {
                    "method": "GET",
                    "path": "/sections/{section}",
                },
            },
        },
    ],
}


def test_expand_api_instruction_body_and_url():
    action = CONTRACT["actions"][0]
    inst = expand_api_instruction(CONTRACT, action, {"query": "shoes"})
    assert inst is not None
    assert inst["type"] == "api_call"
    assert inst["url"] == "https://api.example.com/v1/search"
    assert inst["body"]["q"] == "shoes"
    assert inst["body"]["limit"] == "shoes"
    assert inst["method"] == "POST"


def test_expand_api_instruction_path_params():
    action = CONTRACT["actions"][1]
    inst = expand_api_instruction(CONTRACT, action, {"section": "about"})
    assert inst["url"] == "https://api.example.com/sections/about"
    assert "query" not in inst


def test_expand_execute_steps_browser_api_only():
    steps = expand_execute_steps(CONTRACT, CONTRACT["actions"][0], {"query": "x"})
    assert len(steps) == 1
    assert steps[0]["type"] == "api_call"
