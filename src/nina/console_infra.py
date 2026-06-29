"""Platform infrastructure for the console: validators, rate limiting, logging, metrics.

Framework/cross-cutting concerns shared by the console's middleware and routes,
kept out of ``console_app`` so that module reads as wiring + endpoints. Imports
FastAPI/net_guard but never ``console_app`` (no import cycle).
"""

from __future__ import annotations

import collections
import json
import logging
import os
import threading
import time
import warnings
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .net_guard import SsrfError, validate_public_url


# ── SSRF guard ───────────────────────────────────────────────────────────────
def _validate_external_url(url: str, label: str = "URL") -> None:
    """Raise HTTPException 400 if the URL targets private/loopback addresses.

    Delegates to the shared SSRF guard (which resolves DNS and checks every
    resolved address), translating its error into the API's HTTP envelope.
    """
    try:
        validate_public_url(url, label)
    except SsrfError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── Safe local path resolver ─────────────────────────────────────────────────
_BLOCKED_PATH_PREFIXES = ("/etc/", "/proc/", "/sys/", "/root/", "/boot/", "/dev/")


def _validate_local_path(raw: str) -> Path:
    """Resolve a user-supplied path and block access to system directories."""
    try:
        p = Path(raw).resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path.")
    s = str(p)
    for prefix in _BLOCKED_PATH_PREFIXES:
        if s.startswith(prefix):
            raise HTTPException(status_code=400, detail="Path is in a restricted system directory.")
    return p


# ── In-memory rate limiters ──────────────────────────────────────────────────
class _RateLimiter:
    """Sliding-window rate limiter. NOT shared across processes — use Redis for multi-instance."""

    def __init__(self, per_minute: int) -> None:
        self._max = per_minute
        self._lock = threading.Lock()
        self._hits: dict[str, collections.deque] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        cutoff = now - 60.0
        with self._lock:
            q = self._hits.setdefault(key, collections.deque())
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self._max:
                return False
            q.append(now)
            return True


_IP_LIMITER  = _RateLimiter(per_minute=60)   # per source IP  (DoS)
_KEY_LIMITER = _RateLimiter(per_minute=200)  # per API key    (quota exhaustion)


# ── Structured JSON logging ──────────────────────────────────────────────────
# Per-request correlation id, set by the request-id middleware and emitted on
# every log line so a route log can be matched to its store/LLM operations.
_request_id_var: ContextVar[str] = ContextVar("nina_request_id", default="")


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log: dict[str, Any] = {
            "ts": int(record.created),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        req_id = _request_id_var.get()
        if req_id:
            log["request_id"] = req_id
        for key in ("site_id", "ip", "method", "path", "status", "duration_ms", "error_code", "plan"):
            val = getattr(record, key, None)
            if val is not None:
                log[key] = val
        return json.dumps(log, ensure_ascii=False)


_log_handler = logging.StreamHandler()
_log_handler.setFormatter(_JSONFormatter())
logger = logging.getLogger("nina.console")
logger.addHandler(_log_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

# ── Optional Sentry error tracking ───────────────────────────────────────────
_sentry_dsn = os.environ.get("SENTRY_DSN")
if _sentry_dsn:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=_sentry_dsn, traces_sample_rate=0.05, profiles_sample_rate=0.01)
        logger.info("Sentry initialized")
    except ImportError:
        warnings.warn("SENTRY_DSN is set but sentry-sdk is not installed. Run: pip install sentry-sdk", RuntimeWarning)


# ── In-process metrics ────────────────────────────────────────────────────────
class _Metrics:
    """Lightweight in-process counters. Resets on restart. Use Prometheus for persistence."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.query_total    = 0
        self.query_ok       = 0
        self.query_error    = 0
        self.quota_exceeded = 0
        self.rate_limited   = 0
        self.auth_failed    = 0
        self._latencies: collections.deque = collections.deque(maxlen=1000)

    def record(self, *, ok: bool, latency_ms: int, error_code: str = "") -> None:
        with self._lock:
            self.query_total += 1
            if ok:
                self.query_ok += 1
            else:
                self.query_error += 1
            if error_code == "QUOTA_EXCEEDED":
                self.quota_exceeded += 1
            elif error_code == "RATE_LIMITED":
                self.rate_limited += 1
            elif error_code in ("UNAUTHORIZED",):
                self.auth_failed += 1
            self._latencies.append(latency_ms)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            lats = sorted(self._latencies)
            n = len(lats)
            return {
                "queryTotal":    self.query_total,
                "queryOk":       self.query_ok,
                "queryError":    self.query_error,
                "quotaExceeded": self.quota_exceeded,
                "rateLimited":   self.rate_limited,
                "authFailed":    self.auth_failed,
                "latencyP50Ms":  lats[n // 2]       if n else None,
                "latencyP95Ms":  lats[int(n * 0.95)] if n else None,
                "latencyAvgMs":  int(sum(lats) / n)  if n else None,
            }


METRICS = _Metrics()
