"""Generate onboarding config packs (zip) for merchant developers."""

from __future__ import annotations

import io
import zipfile
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml

README = """# NINA onboarding pack -- 3 steps to a working agent.json

Step 1) Edit api.manifest.yaml
   Change the paths under "actions:" to your real REST endpoints
   (e.g. /api/v1/products/search -> whatever your search API actually is).
   Everything else in this pack already has sensible defaults.

Step 2) Generate + check the contract
   nina-generate .
   nina-validate dist/agent.json --executable

Step 3) Ship it
   - Deploy dist/agent.json to your backend's public/ folder
   - Add the embed snippet from NINA Console (script tag + API key) to your site

That's it. Files in this pack:
- nina.site.yaml      site identity + login/confirm-before-acting rules (all in one file)
- api.manifest.yaml   <- the one file you actually need to edit
- sitemap.xml         URLs for page discovery
- skills/             optional: extra instructions for tricky actions (see skills/loyalty-points.md)

Want separate auth.policy.yaml / risk.policy.yaml files instead of having
those rules inside nina.site.yaml? Generate the pack again with
includeAuth/includeRisk: true and a separate file each. Either way works --
this is just about which is easier for your team to edit.
"""


def _slug(text: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "-" for ch in text.strip())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "site"


def _origin(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return None


def build_nina_site_yaml(
    *,
    site_id: str,
    name: str,
    base_url: str,
    locales: list[str],
    allowed_origins: list[str],
    auth_policy: dict[str, Any] | None = None,
    risk_policy: dict[str, Any] | None = None,
) -> str:
    """auth_policy/risk_policy, when given, are embedded directly as nested
    "auth:"/"risk:" sections -- the simple-onboarding default, so a merchant
    only has to look at one file for "what does NINA need to log in / ask
    before doing". Omit them to keep those rules in separate
    auth.policy.yaml/risk.policy.yaml files instead (see console_pack.py's
    build_onboarding_pack_files include_auth/include_risk)."""
    origins = allowed_origins or ([_origin(base_url)] if _origin(base_url) else [])
    data: dict[str, Any] = {
        "site": {
            "id": site_id,
            "name": name,
            "baseUrl": base_url.rstrip("/"),
            "locales": locales or ["en"],
            "allowedOrigins": origins,
        },
        "generator": {
            "sitemap": "sitemap.xml",
            "docsDir": "docs",
            "crawl": {"maxPages": 50, "respectRobots": True, "delayMs": 500},
        },
        "publish": {"outputDir": "dist", "uploadUrl": ""},
    }
    if auth_policy:
        data["auth"] = auth_policy
    if risk_policy:
        data["risk"] = risk_policy
    return yaml.safe_dump(data, sort_keys=False)


def build_api_manifest(
    *,
    api_base_url: str,
    capabilities: list[str] | None = None,
) -> str:
    caps = {c.lower() for c in (capabilities or ["search", "list_categories"])}
    base = api_base_url.rstrip("/")
    manifest: dict[str, Any] = {
        "apis": {
            "default": {
                "baseUrl": base,
                "description": "Store API",
            }
        },
        "actions": {},
    }
    actions = manifest["actions"]

    if "search" in caps:
        actions["search_products"] = {
            "apiId": "default",
            "method": "POST",
            "path": "/api/v1/products/search",
            "runtime": "server",
            "description": "Search the product catalog by keyword or filters",
            "parameters": {
                "query": {
                    "type": "string",
                    "required": True,
                    "description": "Search terms",
                }
            },
            "bodyTemplate": {"query": "{query}"},
            "risk": "low",
            "availableOn": ["home", "product_list"],
        }

    if "list_categories" in caps or "categories" in caps:
        actions["list_categories"] = {
            "apiId": "default",
            "method": "GET",
            "path": "/api/v1/categories",
            "runtime": "browser",
            "description": "List product categories for browsing",
            "parameters": {},
            "risk": "low",
            "availableOn": ["home", "product_list"],
        }

    if "cart" in caps or "add_to_cart" in caps:
        actions["add_to_cart"] = {
            "apiId": "default",
            "method": "POST",
            "path": "/api/v1/cart/items",
            "runtime": "server",
            "description": "Add a product to the shopping cart",
            "parameters": {
                "productId": {"type": "string", "required": True},
                "quantity": {"type": "integer", "required": False},
            },
            "bodyTemplate": {"productId": "{productId}", "quantity": "{quantity}"},
            "risk": "low",
            "availableOn": ["home", "product_list", "cart"],
        }

    if "checkout" in caps:
        actions["checkout"] = {
            "apiId": "default",
            "method": "POST",
            "path": "/api/v1/checkout",
            "runtime": "server",
            "description": "Place an order and complete checkout",
            "parameters": {},
            "risk": "high",
            "requiresAuth": True,
            "availableOn": ["cart", "checkout"],
        }

    if not actions:
        actions["search_products"] = {
            "apiId": "default",
            "method": "POST",
            "path": "/api/v1/products/search",
            "runtime": "server",
            "description": "Search the product catalog",
            "parameters": {"query": {"type": "string", "required": True}},
            "bodyTemplate": {"query": "{query}"},
            "risk": "low",
            "availableOn": ["home"],
        }

    return yaml.safe_dump(manifest, sort_keys=False)


def _default_auth_policy_dict() -> dict[str, Any]:
    return {
        "loginUrl": "/login",
        "postLoginRedirect": "/",
        "sessionIndicator": {"type": "cookie", "name": "session_id"},
        "gatedActions": ["checkout", "view_account"],
    }


def default_auth_policy() -> str:
    return yaml.safe_dump(_default_auth_policy_dict(), sort_keys=False)


def default_custom_skill_example(*, action_id: str = "apply_loyalty_points") -> str:
    """A worked example a developer can copy/rename for their own custom
    action -- shows the frontmatter format skill_loader.py expects."""
    return (
        "---\n"
        f"name: {action_id.replace('_', '-')}-skill\n"
        f"appliesTo: [{action_id}]\n"
        "description: How to decide when to apply a customer's loyalty points to an order.\n"
        "---\n"
        f"- Only call {action_id} when the user explicitly asks to use, redeem, or apply their "
        "points/rewards -- never apply them automatically just because the user has a balance.\n"
        "- If the user's points balance isn't already in the REFERENCE MAP from an earlier action "
        "in this conversation, ask a clarifying question instead of guessing how many points they have.\n"
        "- State the resulting discount or balance from this action's actual result; never estimate "
        "or round it yourself.\n"
    )


def _default_risk_policy_dict() -> dict[str, Any]:
    return {
        "confirmActions": ["checkout", "place_order"],
        "blockActions": ["export_all_data"],
        "blockPatterns": ["(?i)(password|credit.?card|cvv|ssn)"],
    }


def default_risk_policy() -> str:
    return yaml.safe_dump(_default_risk_policy_dict(), sort_keys=False)


def fetch_or_build_sitemap(
    base_url: str,
    *,
    sitemap_url: str | None = None,
    raw_xml: str | None = None,
) -> tuple[str, str]:
    """Return (xml_content, source_note)."""
    if raw_xml and "<urlset" in raw_xml:
        return raw_xml.strip() + "\n", "uploaded"

    candidates = []
    if sitemap_url:
        candidates.append(sitemap_url)
    base = base_url.rstrip("/")
    candidates.extend([f"{base}/sitemap.xml", f"{base}/sitemap_index.xml"])

    for url in candidates:
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 200 and "<urlset" in resp.text:
                    return resp.text.strip() + "\n", f"fetched:{url}"
        except httpx.HTTPError:
            continue

    minimal = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{base}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>
  <url><loc>{base}/shop</loc><changefreq>daily</changefreq><priority>0.9</priority></url>
  <url><loc>{base}/cart</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>
  <url><loc>{base}/checkout</loc><changefreq>weekly</changefreq><priority>0.6</priority></url>
  <url><loc>{base}/login</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>
</urlset>
"""
    return minimal, "generated_minimal"


def build_onboarding_pack_files(
    *,
    site_id: str,
    site_name: str,
    base_url: str,
    locales: list[str] | None = None,
    markets: list[str] | None = None,
    allowed_origins: list[str] | None = None,
    api_base_url: str | None = None,
    capabilities: list[str] | None = None,
    sitemap_url: str | None = None,
    raw_sitemap_xml: str | None = None,
    include_auth: bool = False,
    include_risk: bool = False,
    include_skills: bool = True,
) -> dict[str, str]:
    """Simple by default: sensible login/confirm-before-acting rules are
    always embedded directly in nina.site.yaml, so a merchant gets a secure
    default without having to touch a policy file. Pass include_auth=True /
    include_risk=True if your team prefers those rules broken out into
    their own auth.policy.yaml / risk.policy.yaml files instead -- when
    present, those separate files take priority over the embedded ones
    (see generator/pipeline.py)."""
    locales = locales or ["en"]
    api_base = (api_base_url or base_url).rstrip("/")
    sitemap_xml, sitemap_source = fetch_or_build_sitemap(
        base_url,
        sitemap_url=sitemap_url,
        raw_xml=raw_sitemap_xml,
    )

    files = {
        "nina.site.yaml": build_nina_site_yaml(
            site_id=site_id,
            name=site_name,
            base_url=base_url,
            locales=locales,
            allowed_origins=allowed_origins or [],
            auth_policy=None if include_auth else _default_auth_policy_dict(),
            risk_policy=None if include_risk else _default_risk_policy_dict(),
        ),
        "api.manifest.yaml": build_api_manifest(
            api_base_url=api_base,
            capabilities=capabilities,
        ),
        "sitemap.xml": sitemap_xml,
        "README.txt": README + f"\nSitemap source: {sitemap_source}\n",
    }
    if include_auth:
        files["auth.policy.yaml"] = default_auth_policy()
    if include_risk:
        files["risk.policy.yaml"] = default_risk_policy()
    if include_skills:
        files["skills/loyalty-points.md"] = default_custom_skill_example()
    if markets:
        files["README.txt"] += f"Markets: {', '.join(markets)}\n"
    return files


def zip_onboarding_pack(files: dict[str, str], *, archive_name: str = "nina-onboarding-pack") -> tuple[bytes, str]:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    filename = f"{archive_name}.zip"
    return buf.getvalue(), filename


def resolve_site_fields(
    site: dict[str, Any] | None,
    *,
    site_name: str | None,
    base_url: str | None,
    locales: list[str] | None,
    markets: list[str] | None,
    allowed_origins: list[str] | None,
) -> dict[str, Any]:
    if site:
        return {
            "site_id": site["id"],
            "site_name": site["name"],
            "base_url": site["baseUrl"],
            "locales": locales or site.get("locales") or ["en"],
            "markets": markets or site.get("markets") or [],
            "allowed_origins": allowed_origins or site.get("allowedOrigins") or [],
        }
    if not site_name or not base_url:
        raise ValueError("Provide siteId or both siteName and baseUrl")
    return {
        "site_id": _slug(site_name),
        "site_name": site_name,
        "base_url": base_url,
        "locales": locales or ["en"],
        "markets": markets or [],
        "allowed_origins": allowed_origins or ([_origin(base_url)] if _origin(base_url) else []),
    }
