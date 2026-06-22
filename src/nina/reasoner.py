"""Capability 1 — multi-step pre-reasoning.

One lightweight LLM call decides whether the message needs a reasoning pass
and, when it does, produces the enrichment in the same call. Detection is
purely LLM-based — no keyword triggers (P3). Fails open: any LLM failure
means no enrichment and the normal turn proceeds.
"""
from .errors import LLMError
from .intent import format_untrusted_user_message, parse_json_text

REASONER_HEADER = "NINA INTERNAL: PRE-REASONING DETECTOR"

_PROMPT = """{header}
You are an internal pre-processing module for {agent_name}. Decide whether the
user's message requires a reasoning pass BEFORE action selection.

A message needs pre-reasoning when external or world knowledge must be applied
to translate the user's goal into concrete, actionable attributes — that is,
the right action or its parameter values cannot be known yet from the literal
message (e.g. "what should I wear for summer?" must first be reasoned into
clothing attributes). A direct, literal command (e.g. "show me sweatshirts",
"track order 123") does NOT need pre-reasoning.

AVAILABLE ACTIONS
{actions}

RECENT CONVERSATION
{history}

{untrusted_message}

Respond with ONLY a single JSON object:
{{"needs_reasoning": boolean,
  "user_goal": string,
  "inferred_attributes": object,
  "suggested_terms": string[],
  "summary": string}}

If needs_reasoning is false, leave the other fields empty. If true: user_goal
states what the user likely wants, inferred_attributes holds concrete inferred
attributes, suggested_terms holds search/parameter terms an action could use,
and summary is a one-sentence account of the reasoning."""


async def maybe_reason(llm, identity, message, actions, state):
    """Returns an enrichment dict or None (pass-through)."""
    action_lines = "\n".join(
        f'- {a["name"]}: {a["description"]}' for a in actions) or "(none)"
    history = "\n".join(
        f'[{e["role"]}] {e["content"][:200]}'
        for e in state.get("history", [])[-6:]) or "(empty)"
    prompt = _PROMPT.format(
        header=REASONER_HEADER,
        agent_name=identity["agentName"],
        actions=action_lines,
        history=history,
        untrusted_message=format_untrusted_user_message(message),
    )
    try:
        text, _usage = await llm.compose(prompt)
    except LLMError:
        return None
    out = parse_json_text(text)
    if not isinstance(out, dict) or not out.get("needs_reasoning"):
        return None
    return {
        "userGoal": str(out.get("user_goal") or ""),
        "inferredAttributes": out.get("inferred_attributes")
            if isinstance(out.get("inferred_attributes"), dict) else {},
        "suggestedTerms": [t for t in (out.get("suggested_terms") or [])
                           if isinstance(t, str)],
        "summary": str(out.get("summary") or out.get("user_goal") or ""),
    }
