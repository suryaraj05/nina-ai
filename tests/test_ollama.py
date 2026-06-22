"""Ollama provider tests — HTTP mocked, no local daemon required."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from nina import Nina
from nina.errors import LLMError
from nina.init import OllamaProvider, build_llm_client, validate_config


def run(coro):
    return asyncio.run(coro)


def test_validate_config_ollama_without_api_key():
    assert validate_config(
        {"llm": {"provider": "ollama", "model": "llama3.2"}}
    ) == []


def test_validate_config_ollama_rejects_bad_api_key_type():
    bad = validate_config(
        {"llm": {"provider": "ollama", "model": "llama3.2", "apiKey": 1}}
    )
    assert "llm.apiKey" in bad


@pytest.mark.asyncio
async def test_ollama_resolve_parses_json():
    provider = OllamaProvider(
        {"provider": "ollama", "model": "llama3.2", "endpoint": "http://localhost:11434"}
    )
    resolution = {
        "resolution": "chitchat",
        "action": None,
        "input": None,
        "missing_fields": [],
        "confidence": 0.9,
        "user_reply": "Hello!",
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "message": {"content": json.dumps(resolution)},
        "prompt_eval_count": 10,
        "eval_count": 5,
    }
    provider._client.post = AsyncMock(return_value=mock_response)

    out, usage = await provider.resolve("system prompt")
    assert out["resolution"] == "chitchat"
    assert usage["promptTokens"] == 10
    assert usage["completionTokens"] == 5


@pytest.mark.asyncio
async def test_ollama_ping_unreachable():
    provider = OllamaProvider(
        {"provider": "ollama", "model": "llama3.2", "endpoint": "http://localhost:11434"}
    )
    provider._client.get = AsyncMock(
        side_effect=httpx.ConnectError("connection refused")
    )
    with pytest.raises(LLMError) as exc:
        await provider.ping()
    assert "Ollama" in exc.value.message


def test_nina_init_with_ollama_mocked_ping():
    nina = Nina()
    client = build_llm_client(
        {"provider": "ollama", "model": "llama3.2", "endpoint": "http://localhost:11434"}
    )

    async def _init():
        with patch("nina.init.build_llm_client", return_value=client):
            with patch.object(client, "ping", new=AsyncMock()):
                return await nina.init(
                    {"llm": {"provider": "ollama", "model": "llama3.2"}}
                )

    res = run(_init())
    assert res["ok"]
    assert res["data"]["llmReady"] is True
