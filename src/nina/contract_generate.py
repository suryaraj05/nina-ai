"""Generate and attach agent contracts from a merchant storefront URL."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from .openapi_probe import build_contract_from_openapi, fetch_openapi_spec, resolve_base_url, spec_url_for
from .static_site_probe import build_contract_from_static_site


def generate_contract_from_url(
    site: dict[str, Any],
    api_base_url: str,
    *,
    runtime: str = "server",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Try OpenAPI first; fall back to static-site DOM probe.

    Returns (contract, meta) where meta includes ``source`` (``openapi`` | ``static``).
    """
    spec_url = spec_url_for(api_base_url)
    try:
        spec = fetch_openapi_spec(spec_url)
        if not isinstance(spec, dict) or not spec.get("paths"):
            raise ValueError("OpenAPI document has no paths.")
        base = resolve_base_url(spec)
        if not str(base).startswith(("http://", "https://")):
            parsed = urlparse(api_base_url)
            base = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else base
        contract = build_contract_from_openapi(spec, base_url=base or None, runtime=runtime)
        if not contract.get("actions"):
            raise ValueError("No operations found in the OpenAPI document.")
        return contract, {
            "source": "openapi",
            "actionsFound": len(contract["actions"]),
            "baseUrl": contract["apis"]["default"]["baseUrl"],
            "runtime": runtime,
        }
    except Exception as openapi_exc:
        try:
            contract, stats = build_contract_from_static_site(
                site_id=site["id"],
                site_name=site["name"],
                base_url=site.get("baseUrl") or api_base_url,
                storefront_url=api_base_url,
                locales=site.get("locales"),
            )
        except Exception as static_exc:
            raise ValueError(
                f"OpenAPI scan failed ({openapi_exc}). "
                f"Static storefront scan also failed ({static_exc})."
            ) from static_exc
        return contract, {
            "source": "static",
            "actionsFound": stats["actions"],
            "baseUrl": site.get("baseUrl") or api_base_url,
            "runtime": "dom",
            "pathsDiscovered": stats["pathsDiscovered"],
            "pagesCrawled": stats["pagesCrawled"],
            "openapiError": str(openapi_exc),
        }
