"""Onboarding pack generation tests."""

import io
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from nina.console_app import STORE, create_app
from nina.console_pack import (
    build_api_manifest,
    build_nina_site_yaml,
    default_custom_skill_example,
    zip_onboarding_pack,
)
from nina.skill_loader import _parse_skill_file


def _reset_store():
    STORE.orgs.clear()
    STORE.sites.clear()
    STORE.api_keys.clear()
    STORE.cli_tokens.clear()
    STORE.webhook_events.clear()


def test_build_nina_site_yaml_contains_required_fields():
    text = build_nina_site_yaml(
        site_id="acme-store",
        name="Acme Store",
        base_url="https://shop.acme.test",
        locales=["en-IN"],
        allowed_origins=["https://shop.acme.test"],
    )
    assert "id: acme-store" in text
    assert "baseUrl: https://shop.acme.test" in text
    assert "sitemap: sitemap.xml" in text


def test_build_api_manifest_capabilities():
    text = build_api_manifest(
        api_base_url="https://api.acme.test",
        capabilities=["search", "cart", "checkout"],
    )
    assert "search_products" in text
    assert "add_to_cart" in text
    assert "checkout" in text


def test_onboarding_pack_zip_endpoint():
    _reset_store()
    client = TestClient(create_app())
    res = client.post(
        "/v1/wizard/onboarding-pack",
        json={
            "siteName": "Pack Store",
            "baseUrl": "https://pack-store.test",
            "locales": ["en"],
            "capabilities": ["search", "checkout"],
            "includeAuth": True,
            "includeRisk": True,
        },
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert "attachment" in res.headers.get("content-disposition", "")

    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        names = set(zf.namelist())
    assert "nina.site.yaml" in names
    assert "api.manifest.yaml" in names
    assert "sitemap.xml" in names
    assert "auth.policy.yaml" in names
    assert "risk.policy.yaml" in names
    assert "README.txt" in names


def test_zip_onboarding_pack_roundtrip():
    files = {"nina.site.yaml": "site:\n  id: x\n", "README.txt": "hello"}
    payload, name = zip_onboarding_pack(files, archive_name="x")
    assert name == "x.zip"
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        assert zf.read("README.txt").decode() == "hello"


def test_default_custom_skill_example_is_a_valid_loadable_skill(tmp_path):
    text = default_custom_skill_example()
    path = tmp_path / "loyalty-points.md"
    path.write_text(text, encoding="utf-8")
    parsed = _parse_skill_file(path)
    assert parsed is not None
    assert parsed["appliesTo"] == ["apply_loyalty_points"]
    assert parsed["name"]
    assert parsed["description"]
    assert parsed["body"]


def test_onboarding_pack_zip_includes_skills_folder_by_default():
    _reset_store()
    client = TestClient(create_app())
    res = client.post(
        "/v1/wizard/onboarding-pack",
        json={
            "siteName": "Pack Store",
            "baseUrl": "https://pack-store.test",
            "locales": ["en"],
            "capabilities": ["search", "checkout"],
        },
    )
    assert res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        names = set(zf.namelist())
        assert "skills/loyalty-points.md" in names
        skill_text = zf.read("skills/loyalty-points.md").decode()
        readme_text = zf.read("README.txt").decode()
    assert "README.txt" in names
    assert "skills/" in readme_text
    assert "appliesTo" in skill_text


def test_onboarding_pack_zip_omits_skills_folder_when_disabled():
    _reset_store()
    client = TestClient(create_app())
    res = client.post(
        "/v1/wizard/onboarding-pack",
        json={
            "siteName": "Pack Store",
            "baseUrl": "https://pack-store.test",
            "locales": ["en"],
            "includeSkills": False,
        },
    )
    assert res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        names = set(zf.namelist())
    assert not any(n.startswith("skills/") for n in names)


def test_simple_default_pack_has_no_separate_policy_files_but_still_embeds_them():
    """The simple-onboarding default (includeAuth/includeRisk both False)
    must ship fewer files -- no auth.policy.yaml / risk.policy.yaml -- while
    still putting sensible login/confirm-before-acting rules *somewhere*
    (embedded in nina.site.yaml), so a merchant who never touches those
    settings still gets a secure default, not a silently empty one."""
    _reset_store()
    client = TestClient(create_app())
    res = client.post(
        "/v1/wizard/onboarding-pack",
        json={
            "siteName": "Pack Store",
            "baseUrl": "https://pack-store.test",
            "locales": ["en"],
            "capabilities": ["search", "checkout"],
        },
    )
    assert res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        names = set(zf.namelist())
        site_yaml = zf.read("nina.site.yaml").decode()
    assert "auth.policy.yaml" not in names
    assert "risk.policy.yaml" not in names
    assert "gatedActions" in site_yaml
    assert "confirmActions" in site_yaml


def test_simple_default_pack_generator_run_actually_enforces_embedded_risk_policy(tmp_path):
    """Prove the embedded auth/risk in nina.site.yaml isn't just text that
    looks right -- running the real generator pipeline against this pack
    must produce an agent.json whose contract.risk.confirmActions actually
    contains "checkout", the same as if a separate risk.policy.yaml had
    been used."""
    from nina.console_pack import build_onboarding_pack_files
    from nina.generator.pipeline import run_pipeline

    files = build_onboarding_pack_files(
        site_id="acme",
        site_name="Acme",
        base_url="https://acme.test",
        api_base_url="https://acme.test",
        capabilities=["search", "checkout"],
        raw_sitemap_xml=(
            '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://acme.test/</loc></url>"
            "<url><loc>https://acme.test/shop</loc></url>"
            "<url><loc>https://acme.test/cart</loc></url>"
            "<url><loc>https://acme.test/checkout</loc></url>"
            "</urlset>"
        ),
    )
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    result = run_pipeline(tmp_path, dry_run=True)
    assert result.ok, result.errors
    risk = (result.contract or {}).get("risk") or {}
    assert "checkout" in risk.get("confirmActions", [])
