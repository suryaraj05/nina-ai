from __future__ import annotations

from pathlib import Path

import pytest

from nina.dev_launcher import default_services, parse_add


def test_default_services_have_explicit_cwd_and_ports():
    services = default_services(console_port=8787, sidecar_port=8001)
    names = [s.name for s in services]
    assert names == ["console", "sidecar"]
    for service in services:
        assert service.cwd.is_dir()
        assert "8787" in service.command or "8001" in service.command


def test_parse_add_splits_name_cwd_and_command():
    service = parse_add("web=../my-shop/apps/web:npm run dev")
    assert service.name == "web"
    assert service.cwd == Path("../my-shop/apps/web")
    assert service.command == ["npm", "run", "dev"]


@pytest.mark.parametrize("bad", ["no-equals-sign", "name=missing-colon", "=cwd:cmd", "name=:cmd", "name=cwd:"])
def test_parse_add_rejects_malformed_spec(bad):
    with pytest.raises(ValueError):
        parse_add(bad)
