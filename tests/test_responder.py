import asyncio

from nina.responder import compose_response


def test_compose_skips_llm_for_navigation_only_passthrough():
    class _LLM:
        async def compose(self, _prompt):
            raise AssertionError("compose should not run for navigation-only results")

    reply, usage = asyncio.run(
        compose_response(
            _LLM(),
            {"agentName": "NINA"},
            {"language": "en"},
            "show me hoodies under 3000",
            "search_products",
            {"ok": True, "query": "hoodies under 3000"},
        )
    )
    assert "Opening search results" in reply
    assert usage == {}
