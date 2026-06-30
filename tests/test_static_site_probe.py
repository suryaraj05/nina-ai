"""Tests for static storefront contract generation (no OpenAPI)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from nina.contract_generate import generate_contract_from_url
from nina.static_site_probe import build_contract_from_static_site, discover_paths


SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>http://127.0.0.1:{port}/</loc></url>
  <url><loc>http://127.0.0.1:{port}/shop</loc></url>
  <url><loc>http://127.0.0.1:{port}/category/hoodies</loc></url>
  <url><loc>http://127.0.0.1:{port}/cart</loc></url>
</urlset>
"""

HOME_HTML = """
<!doctype html><html><body>
  <a href="/shop">Shop</a>
  <a href="/category/t-shirts">T-Shirts</a>
  <script type="module" src="/assets/app.js"></script>
</body></html>
"""

APP_JS = """
const routes = [
  { path: "/new-arrivals", element: null },
  { path: "/product/:id", element: null },
];
"""


class _StorefrontHandler(BaseHTTPRequestHandler):
    port: int = 0

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path in ("/sitemap.xml", "/sitemap_index.xml"):
            body = SITEMAP.format(port=self.server.server_address[1]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/openapi.json":
            self.send_response(404)
            self.end_headers()
            return
        if self.path == "/assets/app.js":
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.end_headers()
            self.wfile.write(APP_JS.encode())
            return
        if self.path in ("/", "/shop", "/cart", "/category/hoodies", "/category/t-shirts", "/new-arrivals"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HOME_HTML.encode())
            return
        self.send_response(404)
        self.end_headers()


@pytest.fixture
def storefront_server():
    srv = HTTPServer(("127.0.0.1", 0), _StorefrontHandler)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown()


def test_discover_paths_from_sitemap_and_js(storefront_server):
    import httpx

    with httpx.Client(timeout=5.0) as client:
        paths = discover_paths(client, storefront_server)
    assert "/shop" in paths
    assert "/category/hoodies" in paths
    assert "/new-arrivals" in paths or "/product/item" in paths


def test_build_contract_from_static_site(storefront_server):
    contract, stats = build_contract_from_static_site(
        site_id="demo-shop",
        site_name="Demo Shop",
        base_url=storefront_server,
        storefront_url=storefront_server,
        max_pages=8,
    )
    assert stats["source"] == "static"
    assert contract["site"]["id"] == "demo-shop"
    action_ids = {a["id"] for a in contract["actions"]}
    assert "navigate" in action_ids
    assert "show_message" in action_ids
    assert "search_products" in action_ids or "open_category" in action_ids
    assert all(a["execute"]["type"] in ("dom", "message") for a in contract["actions"])


def test_generate_contract_falls_back_to_static(storefront_server):
    site = {
        "id": "demo-shop",
        "name": "Demo Shop",
        "baseUrl": storefront_server,
        "locales": ["en"],
    }
    contract, meta = generate_contract_from_url(site, storefront_server)
    assert meta["source"] == "static"
    assert meta["actionsFound"] >= 3
    assert "apis" not in contract or not contract.get("actions")[0]["execute"].get("apiRef")
