"""Optional API key verification and in-memory rate limiting."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx


@dataclass
class RateLimiter:
    max_requests: int = 60
    window_seconds: int = 60
    _hits: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def allow(self, key: str) -> tuple[bool, dict[str, Any]]:
        now = time.time()
        window_start = now - self.window_seconds
        hits = [t for t in self._hits[key] if t > window_start]
        if len(hits) >= self.max_requests:
            return False, {
                "code": "RATE_LIMITED",
                "message": f"Rate limit exceeded ({self.max_requests}/{self.window_seconds}s).",
                "retryAfterSeconds": int(window_start + self.window_seconds - now) + 1,
            }
        hits.append(now)
        self._hits[key] = hits
        return True, {}


def expected_api_key() -> str | None:
    return os.environ.get("NINA_API_KEY") or None


@dataclass
class KeyContext:
    site_id: str | None = None
    origin: str | None = None
    page_url: str | None = None
    client_ip: str | None = None


class KeyVerifier:
    """Common verifier interface used by local demos and hosted Console flows."""

    def verify(self, provided: str | None, ctx: KeyContext | None = None) -> tuple[bool, dict[str, Any] | None]:
        raise NotImplementedError()


class EnvKeyVerifier(KeyVerifier):
    """Backward-compatible single-key verifier based on NINA_API_KEY."""

    def __init__(self, *, expected: str | None = None):
        self.expected = expected if expected is not None else expected_api_key()

    def verify(self, provided: str | None, ctx: KeyContext | None = None) -> tuple[bool, dict[str, Any] | None]:
        if not self.expected:
            return True, None
        if not provided or provided != self.expected:
            return False, {
                "code": "UNAUTHORIZED",
                "message": "Invalid or missing API key.",
            }
        return True, None


class ConsoleKeyVerifier(KeyVerifier):
    """
    Verify publishable keys against a hosted NINA Console endpoint.
    Expects POST {verify_url} to return JSON: { ok: bool, error?: {...} }.
    """

    def __init__(
        self,
        verify_url: str,
        *,
        secret_key: str | None = None,
        timeout_s: float = 5.0,
        allow_origin_fallback: bool = True,
    ):
        self.verify_url = verify_url
        self.secret_key = secret_key
        self.timeout_s = timeout_s
        self.allow_origin_fallback = allow_origin_fallback

    def _infer_origin(self, ctx: KeyContext | None) -> str | None:
        if not ctx:
            return None
        if ctx.origin:
            return ctx.origin
        if ctx.page_url and self.allow_origin_fallback:
            parsed = urlparse(ctx.page_url)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        return None

    def verify(self, provided: str | None, ctx: KeyContext | None = None) -> tuple[bool, dict[str, Any] | None]:
        if not provided:
            return False, {"code": "UNAUTHORIZED", "message": "Missing API key."}
        payload = {
            "apiKey": provided,
            "siteId": (ctx.site_id if ctx else None),
            "origin": self._infer_origin(ctx),
            "pageUrl": (ctx.page_url if ctx else None),
            "clientIp": (ctx.client_ip if ctx else None),
        }
        headers = {"Content-Type": "application/json"}
        if self.secret_key:
            headers["Authorization"] = f"Bearer {self.secret_key}"
        try:
            with httpx.Client(timeout=self.timeout_s, follow_redirects=True) as client:
                resp = client.post(self.verify_url, json=payload, headers=headers)
                resp.raise_for_status()
                body = resp.json() if resp.content else {}
        except Exception as exc:
            return False, {
                "code": "KEY_VERIFIER_ERROR",
                "message": "Could not verify API key with Console.",
                "details": {"reason": str(exc)},
            }

        if not body.get("ok"):
            return False, body.get("error") or {
                "code": "UNAUTHORIZED",
                "message": "API key rejected by Console.",
            }
        return True, None


def build_key_verifier() -> KeyVerifier:
    """
    Build a verifier from env:
    - NINA_CONSOLE_VERIFY_URL + optional NINA_CONSOLE_SECRET_KEY => ConsoleKeyVerifier
    - otherwise fallback to EnvKeyVerifier (NINA_API_KEY)
    """
    verify_url = os.environ.get("NINA_CONSOLE_VERIFY_URL")
    if verify_url:
        return ConsoleKeyVerifier(
            verify_url=verify_url,
            secret_key=os.environ.get("NINA_CONSOLE_SECRET_KEY"),
            timeout_s=float(os.environ.get("NINA_CONSOLE_VERIFY_TIMEOUT", "5")),
        )
    return EnvKeyVerifier()


def verify_api_key(
    provided: str | None,
    *,
    verifier: KeyVerifier | None = None,
    site_id: str | None = None,
    origin: str | None = None,
    page_url: str | None = None,
    client_ip: str | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    """Validate API key using env default or injected verifier."""
    key_verifier = verifier or build_key_verifier()
    ctx = KeyContext(
        site_id=site_id,
        origin=origin,
        page_url=page_url,
        client_ip=client_ip,
    )
    return key_verifier.verify(provided, ctx)
