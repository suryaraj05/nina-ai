"""Phase 5 DX tests — CLI scaffold, validator, debug output, types."""
import asyncio
import json

import pytest

from nina import Nina, validate_action
from nina.cli import SCAFFOLD, main as cli_main


def run(coro):
    return asyncio.run(coro)


VALID_ACTION = {
    "name": "search_things",
    "description": "Searches the catalogue for matching things and returns "
                   "a list. Use for discovery; not for single-item detail.",
    "inputSchema": {"type": "object",
                    "properties": {"query": {"type": "string",
                                             "description": "Search terms."}},
                    "required": ["query"]},
    "handler": lambda inp, ctx: {"results": []},
}


# 1 — CLI scaffold
def test_cli_scaffold(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli_main(["init"]) == 0
    for name in SCAFFOLD:
        assert (tmp_path / name).exists(), name
    # server.py is syntactically valid (full import needs fastapi installed)
    compile((tmp_path / "server.py").read_text(), "server.py", "exec")
    # actions.py defines exactly three valid action definitions
    ns = {}
    exec((tmp_path / "actions.py").read_text(), ns)
    assert len(ns["ACTIONS"]) == 3
    for action in ns["ACTIONS"]:
        assert validate_action(action)["ok"], action["name"]


# 2 — CLI idempotency
def test_cli_never_overwrites(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    cli_main(["init"])
    (tmp_path / "actions.py").write_text("# user edits\n")
    capsys.readouterr()
    cli_main(["init"])
    out = capsys.readouterr().out
    assert out.count("already exists") == len(SCAFFOLD)
    assert (tmp_path / "actions.py").read_text() == "# user edits\n"


# 3 — validate_action does not register
def test_validate_action_is_preflight_only():
    result = validate_action(VALID_ACTION)
    assert result["ok"] and result["data"]["valid"] is True
    nina = Nina()
    assert len(nina._core.registry.all()) == 0   # nothing was registered


# 4 — V7 description-quality warning (advisory)
def test_validate_action_v7_warning():
    action = dict(VALID_ACTION)
    action["description"] = ("A capability concerning the catalogue of "
                             "merchandise items, in regard to availability "
                             "and pricing of inventory units.")
    result = validate_action(action)
    assert result["ok"] is True                  # registration would succeed
    assert any("verb" in w for w in result["warnings"])


# 5 — V8 handler arity
def test_validate_action_v8_arity():
    action = dict(VALID_ACTION)
    action["handler"] = lambda only_input: only_input
    result = validate_action(action)
    assert result["ok"] is False
    assert result["error"]["code"] == "NINA_ACTION_HANDLER_INVALID"
    assert "(input, context)" in result["error"]["message"]


# 6 — debug output
class _Adapter:
    def __call__(self, payload):
        if payload["mode"] == "resolve":
            return {"resolution": "chitchat", "action": None, "input": None,
                    "missing_fields": [], "confidence": 0.9,
                    "user_reply": "Hello! Ask me about the catalogue."}
        return json.dumps({"needs_reasoning": False})


def test_debug_output(capsys):
    nina = Nina()
    res = run(nina.init({"llm": {"provider": "custom", "adapter": _Adapter()},
                         "debug": True}))
    assert res["ok"]
    run(nina.register(VALID_ACTION))
    turn = run(nina.chat("hi there", "dbg-1"))
    assert turn["ok"]
    out = capsys.readouterr().out
    for fragment in ("NINA DEBUG", "transcript   : hi there",
                     "session      : dbg-1", "reasoner     : skipped",
                     "intent       : chitchat", "confidence 0.90",
                     "action       : none", "references   :",
                     "pending      : none", "result shape : none",
                     "response     :", "latency      :",
                     "==="):
        assert fragment in out, fragment


# 7 — types import cleanly
def test_types_import():
    from nina.types import (ActionDefinition, BehaviorConfig,        # noqa: F401
                            ClarificationNeeded, ErrorObject, HooksConfig,
                            IdentityConfig, LLMConfig, NinaConfig,
                            NinaResult, PendingFlow, ReferenceMap,
                            Session, SessionConfig, Turn)
