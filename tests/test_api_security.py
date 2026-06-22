"""API key and rate limiter tests."""

import os

import pytest

from nina.api_security import (
    EnvKeyVerifier,
    KeyContext,
    RateLimiter,
    verify_api_key,
)


def test_verify_api_key_optional(monkeypatch):
    monkeypatch.delenv("NINA_API_KEY", raising=False)
    ok, err = verify_api_key(None)
    assert ok
    assert err is None


def test_verify_api_key_required(monkeypatch):
    monkeypatch.setenv("NINA_API_KEY", "secret-key")
    ok, _ = verify_api_key("secret-key")
    assert ok
    ok, err = verify_api_key("wrong")
    assert not ok
    assert err["code"] == "UNAUTHORIZED"


def test_rate_limiter_blocks():
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.allow("client-a")[0]
    assert limiter.allow("client-a")[0]
    ok, err = limiter.allow("client-a")
    assert not ok
    assert err["code"] == "RATE_LIMITED"


def test_verify_api_key_with_custom_verifier_context():
    verifier = EnvKeyVerifier(expected="abc")
    ok, _ = verify_api_key("abc", verifier=verifier, site_id="s1", origin="https://x.test")
    assert ok


def test_env_key_verifier_rejects_missing():
    verifier = EnvKeyVerifier(expected="abc")
    ok, err = verifier.verify(None, KeyContext(site_id="s1"))
    assert not ok
    assert err["code"] == "UNAUTHORIZED"
