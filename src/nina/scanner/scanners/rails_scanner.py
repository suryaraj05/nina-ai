"""Rails route scanner — extracts from config/routes.rb."""
from __future__ import annotations

import re
from pathlib import Path

from . import BaseScanner, Route

# get '/products', to: 'products#index'
_VERB_RE = re.compile(
    r"(get|post|put|patch|delete)\s+['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
# resources :products — expands to RESTful CRUD
_RESOURCES_RE = re.compile(r"resources?\s+:(\w+)", re.IGNORECASE)
# namespace :admin do
_NAMESPACE_RE = re.compile(r"namespace\s+:(\w+)\s+do", re.IGNORECASE)
# authenticate :user do / before_action :authenticate_user!
_AUTH_RE = re.compile(r"authenticate\s+:|before_action\s+:authenticate|devise_for", re.IGNORECASE)

_RESTFUL = [
    ("GET",    "/{name}"),
    ("POST",   "/{name}"),
    ("GET",    "/{name}/new"),
    ("GET",    "/{name}/{id}"),
    ("GET",    "/{name}/{id}/edit"),
    ("PUT",    "/{name}/{id}"),
    ("PATCH",  "/{name}/{id}"),
    ("DELETE", "/{name}/{id}"),
]


class RailsScanner(BaseScanner):
    def scan(self, project: Path) -> list[Route]:
        routes: list[Route] = []
        routes_rb = project / "config" / "routes.rb"
        if not routes_rb.exists():
            return routes
        try:
            text = routes_rb.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return routes
        rel = str(routes_rb.relative_to(project)).replace("\\", "/")
        routes.extend(self._scan_routes(text, rel))
        return routes

    def _scan_routes(self, text: str, rel: str) -> list[Route]:
        routes: list[Route] = []
        lines = text.splitlines()
        namespace_stack: list[str] = []
        in_auth_block = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Track namespace blocks
            ns_m = _NAMESPACE_RE.search(stripped)
            if ns_m:
                namespace_stack.append(ns_m.group(1))
            if stripped == "end" and namespace_stack:
                namespace_stack.pop()

            if _AUTH_RE.search(stripped):
                in_auth_block = True

            prefix = "/" + "/".join(namespace_stack) if namespace_stack else ""
            role = "admin" if any(n in ("admin", "superadmin") for n in namespace_stack) else "customer"

            # resources :name
            res_m = _RESOURCES_RE.search(stripped)
            if res_m:
                name = res_m.group(1)
                for method, path_tmpl in _RESTFUL:
                    path = prefix + path_tmpl.format(name=name)
                    routes.append(Route(
                        path=path,
                        method=method,
                        auth_required=in_auth_block,
                        role=role,
                        path_params=self._extract_path_params(path),
                        source_file=rel,
                        source_line=i + 1,
                        tags=["rails"],
                    ))
                continue

            # Explicit verb routes
            verb_m = _VERB_RE.search(stripped)
            if verb_m:
                method = verb_m.group(1).upper()
                path = prefix + "/" + verb_m.group(2).strip("/")
                routes.append(Route(
                    path=path,
                    method=method,
                    auth_required=in_auth_block,
                    role=role,
                    path_params=self._extract_path_params(path),
                    source_file=rel,
                    source_line=i + 1,
                    tags=["rails"],
                ))

        return routes
