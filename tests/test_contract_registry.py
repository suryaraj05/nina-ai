"""Contract registry auto-registration tests."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from nina.contract_registry import (
    contract_actions_for_registry,
    make_api_handler,
    register_from_contract,
)


SAMPLE_CONTRACT = {
    "site": {"id": "t", "name": "T", "baseUrl": "http://127.0.0.1:9000"},
    "apis": {"default": {"baseUrl": "http://127.0.0.1:9000"}},
    "actions": [
        {
            "id": "search",
            "description": "Search the catalog by keyword",
            "parameters": {"query": {"type": "string", "required": True}},
            "execute": {
                "type": "api",
                "runtime": "server",
                "apiRef": {
                    "method": "POST",
                    "path": "/api/search",
                    "bodyTemplate": {"query": "{query}"},
                },
            },
        },
        {
            "id": "browse",
            "description": "Browse categories in the browser",
            "parameters": {},
            "execute": {
                "type": "api",
                "runtime": "browser",
                "apiRef": {"method": "GET", "path": "/api/categories"},
            },
        },
    ],
}


def test_contract_actions_includes_all_with_mode():
    specs = contract_actions_for_registry(SAMPLE_CONTRACT)
    by_name = {s["name"]: s for s in specs}
    assert by_name["search"]["_mode"] == "server_api"
    assert by_name["browse"]["_mode"] == "passthrough"


def test_make_api_handler_success():
    handler = make_api_handler(SAMPLE_CONTRACT, SAMPLE_CONTRACT["actions"][0])
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": [{"id": "1"}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.request.return_value = mock_resp
        out = handler({"query": "hoodie"}, {"sessionId": "s1"})

    assert out["results"][0]["id"] == "1"
    client.request.assert_called_once()
    call = client.request.call_args
    assert call[0][0] == "POST"
    assert call[1]["json"] == {"query": "hoodie"}


@pytest.mark.asyncio
async def test_register_from_contract():
    nina = MagicMock()
    nina.register = MagicMock(return_value={"ok": True})

    async def _register(spec):
        return {"ok": True}

    nina.register = _register
    result = await register_from_contract(nina, SAMPLE_CONTRACT)
    assert "search" in result["registered"]
    assert "browse" in result["registered"]
    assert not result["failed"]
