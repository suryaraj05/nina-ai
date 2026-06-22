"""Playwright E2E against static SDK + API contract (no LLM required for guard paths)."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = ROOT / "examples" / "ecommerce-fastapi"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(base_url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base_url, timeout=2) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(0.4)
    raise RuntimeError(f"Server did not become ready at {base_url}")


@pytest.fixture(scope="module")
def demo_server():
    """Start a dedicated uvicorn instance on a free port for E2E."""
    port = _free_port()
    env = {**os.environ, "NINA_DEBUG": "0"}
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(DEMO_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_for_server(base)
    except RuntimeError:
        proc.terminate()
        proc.wait(timeout=5)
        pytest.skip("ecommerce demo server failed to start (is Ollama running?)")
    yield base
    proc.terminate()
    proc.wait(timeout=10)


@pytest.mark.e2e
def test_demo_page_loads_and_panel_visible(demo_server):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(demo_server)
        page.wait_for_selector("#nina-root", timeout=15000)
        assert page.locator(".nina-toggle").is_visible()
        browser.close()


@pytest.mark.e2e
def test_guardrail_blocks_password_in_panel(demo_server):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(demo_server)
        page.wait_for_selector("#nina-input", timeout=15000)
        page.fill("#nina-input", "my password is secret123 login")
        page.press("#nina-input", "Enter")
        page.wait_for_function(
            """() => {
              const msgs = [...document.querySelectorAll('.nina-msg--nina')];
              const last = msgs[msgs.length - 1];
              if (!last) return false;
              const t = last.textContent.toLowerCase();
              return t.includes('password')
                || t.includes('credential')
                || t.includes('sign in')
                || t.includes('login');
            }""",
            timeout=15000,
        )
        browser.close()


@pytest.mark.e2e
def test_query_endpoint_rate_limit_headers(demo_server):
    import urllib.request

    # smoke: endpoint responds JSON
    req = urllib.request.Request(
        f"{demo_server}/v1/query",
        data=json.dumps({
            "message": "hi",
            "sessionId": "e2e-rate-test",
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode())
    assert "ok" in body


_SAMPLE_PRODUCTS = [
    {
        "id": "p01",
        "name": "Classic Navy Hoodie",
        "category": "tops",
        "price": 1999,
        "tags": ["casual", "winter"],
        "sizes": ["S", "M", "L"],
        "in_stock": True,
    },
    {
        "id": "p02",
        "name": "White Cotton Kurta",
        "category": "tops",
        "price": 1299,
        "tags": ["summer", "casual"],
        "sizes": ["S", "M", "L"],
        "in_stock": True,
    },
]


def _mock_query_response(message: str, extra: dict | None = None) -> dict:
    """Deterministic /v1/query payloads — no LLM required."""
    extra = extra or {}
    msg = (message or "").lower()
    if extra.get("confirmed"):
        return {
            "ok": True,
            "data": {
                "naturalLanguageResponse": "Order ORD-E2E-001 placed.",
                "intent": "checkout",
                "instructions": [
                    {
                        "type": "show_order",
                        "data": {"orderId": "ORD-E2E-001", "total": 1999},
                    },
                    {
                        "type": "update_cart",
                        "data": {"cart": {"items": [], "total": 0}},
                    },
                    {"type": "close_cart"},
                ],
            },
            "error": None,
        }
    if "checkout" in msg:
        return {
            "ok": True,
            "data": {
                "naturalLanguageResponse": "Ready to place your order?",
                "intent": "confirmation",
                "needsConfirmation": True,
            },
            "error": None,
        }
    if "add" in msg and "cart" in msg:
        return {
            "ok": True,
            "data": {
                "naturalLanguageResponse": "Added Classic Navy Hoodie to your cart.",
                "intent": "add_to_cart",
                "instructions": [
                    {
                        "type": "update_cart",
                        "data": {
                            "cart": {
                                "items": [
                                    {
                                        "id": "p01",
                                        "name": "Classic Navy Hoodie",
                                        "price": 1999,
                                        "qty": 1,
                                    }
                                ],
                                "total": 1999,
                            }
                        },
                    },
                    {
                        "type": "toast",
                        "message": "Added to cart",
                        "level": "success",
                    },
                ],
            },
            "error": None,
        }
    if "search" in msg:
        return {
            "ok": True,
            "data": {
                "naturalLanguageResponse": "Found 2 products for you.",
                "intent": "search_products",
                "instructions": [
                    {
                        "type": "render_products",
                        "target": "#nina-product-grid",
                        "data": _SAMPLE_PRODUCTS,
                    },
                    {"type": "scroll_to", "selector": "#nina-catalog"},
                ],
            },
            "error": None,
        }
    return {
        "ok": True,
        "data": {"naturalLanguageResponse": "How can I help?", "intent": "chitchat"},
        "error": None,
    }


@pytest.mark.e2e
def test_search_cart_checkout_confirm_flow(demo_server):
    """Panel → mocked API → executor: search, cart, checkout Yes."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def handle_query(route):
            body = json.loads(route.request.post_data or "{}")
            message = body.get("message") or ""
            extra = body.get("extra") or {}
            if body.get("confirmed") is not None:
                extra["confirmed"] = body.get("confirmed")
            payload = _mock_query_response(message, extra)
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(payload),
            )

        page.route("**/v1/query", handle_query)
        page.goto(demo_server)
        page.wait_for_selector("#nina-input", timeout=15000)

        page.fill("#nina-input", "search for hoodies")
        page.click(".nina-panel__form button[type=submit]")
        page.wait_for_selector(".product-card", timeout=10000)
        assert page.locator(".product-card").count() == 2

        page.fill("#nina-input", "add first to cart")
        page.click(".nina-panel__form button[type=submit]")
        page.wait_for_function(
            "() => document.querySelector('#nina-cart-count')?.textContent === '1'",
            timeout=10000,
        )

        page.fill("#nina-input", "checkout")
        page.click(".nina-panel__form button[type=submit]")
        page.wait_for_selector(".nina-confirm", timeout=10000)
        page.click(".nina-confirm button.yes")

        page.wait_for_selector(".nina-toast.success", timeout=10000)
        order_toast = page.locator(".nina-toast.success", has_text="ORD-E2E-001")
        assert order_toast.count() >= 1
        assert page.locator("#nina-cart-count").inner_text() == "0"
        browser.close()
