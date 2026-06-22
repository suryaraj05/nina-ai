"""Dual-path inference: deterministic literal-command matching that bypasses
the LLM entirely, falling through unchanged to the LLM path on a miss."""
from __future__ import annotations

import asyncio
import time

import pytest

from nina import Nina
from nina.fast_path import compile_fast_path_patterns, try_fast_path
from nina.skill_loader import BUILTIN_SKILLS_DIR, load_skills

ACTIONS = [
    {"name": "search_products", "examples": []},
    {"name": "list_categories", "examples": ["what categories do you have"]},
    {"name": "checkout", "examples": []},
]


def run(coro):
    return asyncio.run(coro)


def test_skill_pattern_extracts_named_param():
    skills = load_skills(BUILTIN_SKILLS_DIR)
    patterns = compile_fast_path_patterns(skills)
    match = try_fast_path("search for gaming laptops", ACTIONS, patterns)
    assert match == {"action": "search_products", "input": {"query": "gaming laptops"}}


def test_skill_pattern_is_case_insensitive_and_trims_whitespace():
    skills = load_skills(BUILTIN_SKILLS_DIR)
    patterns = compile_fast_path_patterns(skills)
    match = try_fast_path("  SEARCH FOR   wireless mice  ", ACTIONS, patterns)
    assert match == {"action": "search_products", "input": {"query": "wireless mice"}}


def test_goal_phrasing_needing_reasoning_is_not_fast_pathed():
    """'show me X' style phrasing is deliberately NOT a fast-path trigger:
    it often carries a goal that needs reasoning before search (e.g. season
    -> fabric/sleeve-length attributes), and a literal fast path would search
    for the unreasoned sentence verbatim and silently skip that reasoning."""
    skills = load_skills(BUILTIN_SKILLS_DIR)
    patterns = compile_fast_path_patterns(skills)
    match = try_fast_path(
        "show me the dressing that I can wear for summer season", ACTIONS, patterns
    )
    assert match is None


def test_exact_example_match_is_zero_config():
    match = try_fast_path("What categories do you have?", ACTIONS, [])
    assert match == {"action": "list_categories", "input": {}}


def test_normalized_action_name_match():
    match = try_fast_path("list categories", ACTIONS, [])
    assert match == {"action": "list_categories", "input": {}}


def test_no_match_returns_none():
    assert try_fast_path("what's the weather like", ACTIONS, []) is None


def test_excluded_actions_never_fast_path_even_with_exact_name_match():
    match = try_fast_path("checkout", ACTIONS, [], excluded_actions=frozenset({"checkout"}))
    assert match is None


def test_unregistered_action_in_pattern_is_ignored():
    skills = load_skills(BUILTIN_SKILLS_DIR)
    patterns = compile_fast_path_patterns(skills)
    actions_without_search = [a for a in ACTIONS if a["name"] != "search_products"]
    assert try_fast_path("search for laptops", actions_without_search, patterns) is None


def test_fast_path_bypasses_llm_entirely_end_to_end():
    llm_calls: list[dict] = []

    def adapter(payload):
        llm_calls.append(payload)
        return {"resolution": "chitchat", "user_reply": "should never be reached", "confidence": 1.0}

    async def scenario():
        nina = Nina()
        await nina.init({"llm": {"provider": "custom", "adapter": adapter}})
        await nina.register({
            "name": "search_products",
            "description": "Search the product catalog by keyword.",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "search terms"}},
                "required": ["query"],
            },
            "handler": lambda inp, ctx: {"results": [], "count": 0},
        })
        return await nina.chat("search for gaming laptops", "s1")

    envelope = run(scenario())
    resolve_calls = [c for c in llm_calls if c.get("mode") != "compose"]
    assert not resolve_calls, "the resolution LLM call ran even though the fast path should have matched"
    data = envelope["data"]
    assert data["actionCalled"] == "search_products"
    assert data["actionInput"] == {"query": "gaming laptops"}
    assert data["confidence"] == 1.0


def test_ambiguous_message_still_falls_through_to_the_llm():
    llm_calls: list[dict] = []

    def adapter(payload):
        llm_calls.append(payload)
        return {"resolution": "action", "action": "search_products",
                "input": {"query": "something nice"}, "confidence": 0.9}

    async def scenario():
        nina = Nina()
        await nina.init({"llm": {"provider": "custom", "adapter": adapter}})
        await nina.register({
            "name": "search_products",
            "description": "Search the product catalog by keyword.",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "search terms"}},
                "required": ["query"],
            },
            "handler": lambda inp, ctx: {"results": [], "count": 0},
        })
        return await nina.chat("I need a gift idea for someone who likes hiking", "s1")

    envelope = run(scenario())
    resolve_calls = [c for c in llm_calls if c.get("mode") != "compose"]
    assert resolve_calls, "LLM should have been consulted for this non-literal phrasing"


def test_fast_path_is_at_least_two_orders_of_magnitude_faster_than_simulated_llm_latency():
    skills = load_skills(BUILTIN_SKILLS_DIR)
    patterns = compile_fast_path_patterns(skills)
    started = time.perf_counter()
    for _ in range(100):
        try_fast_path("search for noise cancelling headphones", ACTIONS, patterns)
    elapsed_per_call_ms = (time.perf_counter() - started) / 100 * 1000
    assert elapsed_per_call_ms < 5, f"fast path took {elapsed_per_call_ms:.3f}ms/call, expected < 5ms"
