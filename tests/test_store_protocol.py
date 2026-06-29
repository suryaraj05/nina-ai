"""Guard: ConsoleStore and PgStore must both satisfy the Store Protocol.

The two stores have silently drifted before (an API-key hashing divergence that
broke JSON<->Postgres migration). This test fails fast if either implementation
drops or never adds a method the Store contract requires, so they can't diverge
again unnoticed.
"""

from __future__ import annotations

from nina.console_app import ConsoleStore
from nina.pg_store import PgStore
from nina.store import STORE_METHODS, Store


def _public_methods(cls: type) -> set[str]:
    return {n for n in dir(cls) if not n.startswith("_") and callable(getattr(cls, n))}


def test_console_store_implements_every_protocol_method():
    missing = STORE_METHODS - _public_methods(ConsoleStore)
    assert not missing, f"ConsoleStore is missing Store methods: {sorted(missing)}"


def test_pg_store_implements_every_protocol_method():
    missing = STORE_METHODS - _public_methods(PgStore)
    assert not missing, f"PgStore is missing Store methods: {sorted(missing)}"


def test_console_store_is_runtime_instance_of_store():
    # ConsoleStore is cheap to instantiate (no DB); runtime_checkable Protocol
    # verifies the concrete object exposes the full surface.
    assert isinstance(ConsoleStore(), Store)


def test_protocol_surface_is_nonempty_and_sane():
    # Sanity: catches an accidentally-empty/broken Protocol that would make the
    # drift checks above vacuously pass.
    assert len(STORE_METHODS) >= 30
    assert {"create_org", "create_site", "issue_api_key", "attach_contract"} <= STORE_METHODS
