"""Integration: guardrails block before LLM in chat path."""

import pytest

from nina import Nina


@pytest.mark.asyncio
async def test_chat_blocks_credential_paste():
    nina = Nina()
    await nina.init({
        "llm": {
            "provider": "custom",
            "model": "test",
            "adapter": lambda _: (_ for _ in ()).throw(AssertionError("LLM should not run")),
        },
        "security": {"enableCredentialBlock": True, "enableInjectionGuard": True},
    })
    await nina.register({
        "name": "search_products",
        "description": "Search",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": lambda _: {"ok": True},
    })
    envelope = await nina.chat("my password is secret123 login", "sess-guard-1")
    assert envelope["ok"]
    turn = envelope["data"]
    assert turn["intent"] == "blocked"
    assert turn.get("guardrail", {}).get("code") == "CREDENTIAL_DETECTED"
    assert turn.get("instructions")
