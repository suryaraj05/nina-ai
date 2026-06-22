"""Deterministic correction of id-shaped params the LLM fabricated from a
slug/title instead of copying the real id out of the reference map."""
from __future__ import annotations

from nina.session import resolve_reference_parameters

STATE = {
    "referenceMap": {
        "lastSearchResults": [
            {"index": 1, "sourceAction": "search_products", "id": "cm9x7k2p1q003z", "title": "ProBook Air 14"},
            {"index": 2, "sourceAction": "search_products", "id": "cm9x7k2p1q004a", "title": "CloudBook Lite"},
        ],
        "lastSingleItem": None,
    }
}


def test_corrects_slug_derived_id_to_real_id():
    out = resolve_reference_parameters(STATE, {"variantId": "probook-air-14", "quantity": 1})
    assert out == {"variantId": "cm9x7k2p1q003z", "quantity": 1}


def test_leaves_already_correct_id_untouched():
    out = resolve_reference_parameters(STATE, {"variantId": "cm9x7k2p1q004a"})
    assert out["variantId"] == "cm9x7k2p1q004a"


def test_leaves_unmatched_value_untouched_rather_than_guessing():
    out = resolve_reference_parameters(STATE, {"variantId": "totally-unrelated-product"})
    assert out["variantId"] == "totally-unrelated-product"


def test_ignores_non_id_shaped_params():
    out = resolve_reference_parameters(STATE, {"query": "probook-air-14"})
    assert out["query"] == "probook-air-14"


def test_no_reference_map_is_a_no_op():
    out = resolve_reference_parameters({}, {"variantId": "probook-air-14"})
    assert out == {"variantId": "probook-air-14"}
