"""Django route scanner — extracts from urls.py and ViewSet routers."""
from __future__ import annotations

import re
from pathlib import Path

from . import BaseScanner, Route

# path("products/search/", views.product_search, name="product-search")
_PATH_RE = re.compile(
    r'(?:path|re_path)\s*\(\s*["\']([^"\']+)["\'].*?(?:views|viewsets)?\.?(\w+)',
)
# router.register(r"products", ProductViewSet)
_ROUTER_RE = re.compile(
    r'router\.register\s*\(\s*r?["\']([^"\']+)["\'].*?(\w+ViewSet)',
)
# @login_required, @permission_classes([IsAuthenticated])
_AUTH_RE = re.compile(
    r'@login_required|IsAuthenticated|permission_required|@staff_member_required',
    re.IGNORECASE,
)
_ADMIN_RE = re.compile(r'admin\.site|AdminSite|ModelAdmin|/admin/', re.IGNORECASE)

# ViewSet HTTP methods expand to standard REST routes
_VIEWSET_METHODS = [
    ("GET",    "{base}/"),
    ("POST",   "{base}/"),
    ("GET",    "{base}/{id}/"),
    ("PUT",    "{base}/{id}/"),
    ("PATCH",  "{base}/{id}/"),
    ("DELETE", "{base}/{id}/"),
]


class DjangoScanner(BaseScanner):
    def scan(self, project: Path) -> list[Route]:
        routes: list[Route] = []
        urls_files = [
            f for f in project.rglob("urls.py")
            if "site-packages" not in str(f)
        ]
        views_files = [
            f for f in project.rglob("views.py")
            if "site-packages" not in str(f)
        ]
        views_text = "\n".join(
            f.read_text(encoding="utf-8", errors="ignore")
            for f in views_files
            if f.exists()
        )

        for filepath in urls_files:
            try:
                text = filepath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = str(filepath.relative_to(project)).replace("\\", "/")
            routes.extend(self._scan_urls(text, views_text, rel))
        return routes

    def _scan_urls(self, text: str, views_text: str, rel: str) -> list[Route]:
        routes: list[Route] = []

        # Regular path() entries
        for i, line in enumerate(text.splitlines()):
            m = _PATH_RE.search(line)
            if m:
                raw_path = "/" + m.group(1).lstrip("/")
                handler = m.group(2)
                # Find auth in views file near this handler definition
                handler_block = self._find_handler_block(views_text, handler)
                auth = bool(_AUTH_RE.search(handler_block + line))
                role = self._infer_role(raw_path, handler)
                # Skip Django admin internals
                if bool(_ADMIN_RE.search(raw_path)):
                    continue
                routes.append(Route(
                    path=self._django_to_openapi(raw_path),
                    method="GET",  # Django urls don't specify method; default to GET
                    auth_required=auth,
                    role=role,
                    path_params=self._extract_path_params(raw_path),
                    handler_name=handler,
                    source_file=rel,
                    source_line=i + 1,
                    tags=["django"],
                ))

            # ViewSet router registration — expands to CRUD routes
            r = _ROUTER_RE.search(line)
            if r:
                base = "/" + r.group(1).strip("/")
                viewset = r.group(2)
                for method, path_tmpl in _VIEWSET_METHODS:
                    path = path_tmpl.format(base=base)
                    handler_block = self._find_handler_block(views_text, viewset)
                    auth = bool(_AUTH_RE.search(handler_block))
                    role = self._infer_role(path, viewset)
                    routes.append(Route(
                        path=path,
                        method=method,
                        auth_required=auth,
                        role=role,
                        path_params=self._extract_path_params(path),
                        handler_name=viewset,
                        source_file=rel,
                        source_line=i + 1,
                        tags=["django", "viewset"],
                    ))

        return routes

    @staticmethod
    def _find_handler_block(views_text: str, handler: str) -> str:
        """Return ~30 lines starting from handler definition in views.py."""
        idx = views_text.find(f"def {handler}")
        if idx == -1:
            idx = views_text.find(f"class {handler}")
        if idx == -1:
            return ""
        return views_text[idx : idx + 800]

    @staticmethod
    def _django_to_openapi(path: str) -> str:
        """Convert Django <int:id> style params to {id} OpenAPI style."""
        return re.sub(r'<(?:\w+:)?(\w+)>', r'{\1}', path)
