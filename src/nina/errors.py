"""Error catalog (spec §5), universal result envelope, internal signal types."""
from datetime import datetime, timezone

# code -> (category, retryable)
CATALOG = {
    "NINA_CONFIG_INVALID":             ("config", False),
    "NINA_ADAPTER_INVALID":            ("config", False),
    "NINA_STORE_INVALID":              ("config", False),
    "NINA_ALREADY_INITIALIZED":        ("config", False),
    "NINA_NOT_INITIALIZED":            ("config", False),
    "NINA_ACTION_NAME_INVALID":        ("registration", False),
    "NINA_ACTION_DUPLICATE":           ("registration", False),
    "NINA_ACTION_DESCRIPTION_INVALID": ("registration", False),
    "NINA_ACTION_SCHEMA_INVALID":      ("registration", False),
    "NINA_ACTION_HANDLER_INVALID":     ("registration", False),
    "NINA_MESSAGE_INVALID":            ("input", False),
    "NINA_SESSION_ID_INVALID":         ("input", False),
    "NINA_NO_ACTIONS_REGISTERED":      ("input", False),
    "NINA_LLM_UNREACHABLE":            ("llm", True),
    "NINA_LLM_AUTH_FAILED":            ("llm", False),
    "NINA_LLM_RATE_LIMITED":           ("llm", True),
    "NINA_LLM_RESPONSE_MALFORMED":     ("llm", True),
    "ACTION_TIMEOUT":                  ("action", True),
    "ACTION_RUNTIME_ERROR":            ("action", False),
    "ACTION_DOMAIN_ERROR":             ("action", False),
    "ACTION_INPUT_REJECTED":           ("action", False),
    "NINA_SESSION_NOT_FOUND":          ("session", False),
    "NINA_SESSION_DATA_INVALID":       ("session", False),
    "NINA_SESSION_STORE_FAILURE":      ("session", True),
    "NINA_INTERNAL":                   ("internal", True),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def error_object(code: str, message: str, details: dict | None = None) -> dict:
    category, retryable = CATALOG.get(code, ("internal", True))
    return {
        "code": code,
        "message": message,
        "category": category,
        "retryable": retryable,
        "details": details,
        "timestamp": now_iso(),
    }


def ok(data) -> dict:
    return {"ok": True, "data": data, "error": None}


def fail(code: str, message: str, details: dict | None = None) -> dict:
    return {"ok": False, "data": None, "error": error_object(code, message, details)}


class LLMError(Exception):
    """Internal-only. Converted to an envelope error at the public boundary (P2)."""
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details


class StoreError(Exception):
    """Internal-only. Custom session store failure."""
    def __init__(self, op: str, reason: str):
        super().__init__(reason)
        self.op, self.reason = op, reason
