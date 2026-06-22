"""Laravel route scanner — extracts from routes/api.php and routes/web.php."""
from __future__ import annotations

import re
from pathlib import Path

from . import BaseScanner, Route

# Route::get('/products', [ProductController::class, 'index']);
# Route::post('/orders', 'OrderController@store');
_ROUTE_RE = re.compile(
    r"Route::(get|post|put|patch|delete|any)\s*\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
# Route::middleware(['auth:sanctum'])->group(...)
_AUTH_MIDDLEWARE_RE = re.compile(
    r"middleware\s*\(\s*\[?['\"](?:auth|sanctum|jwt|api\.auth|verified)['\"]",
    re.IGNORECASE,
)
# Route::prefix('/admin')->...
_PREFIX_RE = re.compile(r"prefix\s*\(\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
_COLON_PARAM_RE = re.compile(r'\{(\w+)\??}')


class LaravelScanner(BaseScanner):
    def scan(self, project: Path) -> list[Route]:
        routes: list[Route] = []
        route_files = []
        for name in ("api.php", "web.php"):
            f = project / "routes" / name
            if f.exists():
                route_files.append(f)
        for filepath in route_files:
            try:
                text = filepath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = str(filepath.relative_to(project)).replace("\\", "/")
            routes.extend(self._scan_file(text, rel))
        return routes

    def _scan_file(self, text: str, rel: str) -> list[Route]:
        routes: list[Route] = []
        lines = text.splitlines()

        # Detect if we're inside an auth middleware group
        in_auth_group = False

        for i, line in enumerate(lines):
            if _AUTH_MIDDLEWARE_RE.search(line):
                in_auth_group = True
            if "});" in line and in_auth_group:
                in_auth_group = False

            m = _ROUTE_RE.search(line)
            if not m:
                continue
            method = m.group(1).upper()
            if method == "ANY":
                method = "GET"
            path = "/" + m.group(2).strip("/")
            # Laravel params: {id} or {id?} (optional)
            path_params = _COLON_PARAM_RE.findall(path)
            # Normalize to OpenAPI style (already curly-brace style in Laravel)

            auth = in_auth_group or bool(_AUTH_MIDDLEWARE_RE.search(line))
            role = self._infer_role(path)
            routes.append(Route(
                path=path,
                method=method,
                auth_required=auth,
                role=role,
                path_params=path_params,
                source_file=rel,
                source_line=i + 1,
                tags=["laravel"],
            ))
        return routes
