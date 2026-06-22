"""Tests for LLM config seal/unseal (at-rest encryption)."""
import os
import warnings

import pytest
from cryptography.fernet import Fernet

from nina.crypto import _SEAL_MARKER, seal_llm_config, unseal_llm_config


@pytest.fixture()
def fernet_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("NINA_ENCRYPT_KEY", key)
    return key


@pytest.fixture()
def no_key(monkeypatch):
    monkeypatch.delenv("NINA_ENCRYPT_KEY", raising=False)


def test_seal_produces_sealed_blob(fernet_key):
    config = {"provider": "openai", "apiKey": "sk-secret", "model": "gpt-4o"}
    sealed = seal_llm_config(config)
    assert _SEAL_MARKER in sealed
    assert "apiKey" not in sealed
    assert "provider" not in sealed


def test_unseal_recovers_original(fernet_key):
    config = {"provider": "openai", "apiKey": "sk-secret", "model": "gpt-4o"}
    sealed = seal_llm_config(config)
    recovered = unseal_llm_config(sealed)
    assert recovered == config


def test_seal_unseal_roundtrip_nested(fernet_key):
    config = {"provider": "custom", "adapter": "placeholder", "nested": {"x": 1}}
    assert unseal_llm_config(seal_llm_config(config)) == config


def test_unseal_plaintext_passthrough(fernet_key):
    """Configs without _sealed key pass through unchanged."""
    plain = {"provider": "custom", "adapter": "fn"}
    assert unseal_llm_config(plain) == plain


def test_seal_without_key_warns_and_returns_plaintext(no_key):
    config = {"provider": "openai", "apiKey": "sk-secret"}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = seal_llm_config(config)
    assert result == config
    assert any("NINA_ENCRYPT_KEY" in str(w.message) for w in caught)


def test_unseal_without_key_raises_when_sealed(no_key):
    """A sealed blob cannot be decrypted without the key."""
    key = Fernet.generate_key().decode()
    os.environ["NINA_ENCRYPT_KEY"] = key
    try:
        sealed = seal_llm_config({"apiKey": "sk-x"})
    finally:
        del os.environ["NINA_ENCRYPT_KEY"]
    with pytest.raises(RuntimeError, match="NINA_ENCRYPT_KEY"):
        unseal_llm_config(sealed)


def test_seal_empty_config_passthrough(fernet_key):
    assert seal_llm_config({}) == {}


def test_unseal_empty_config_passthrough(fernet_key):
    assert unseal_llm_config({}) == {}
