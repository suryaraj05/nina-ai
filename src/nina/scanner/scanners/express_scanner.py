"""Express.js route scanner — extracts routes from app.get/router.post calls."""
from __future__ import annotations

import re
from pathlib import Path

from . import BaseScanner, Route

_ROUTE_RE = re.compile(
    r'(?:app|router)\.(get|post|put|patch|delete|head|options)\s*\(\s*["\`\']([^"\'`\)]+)["\`\']',
    re.IGNORECASE,
)
# router.use('/prefix', subRouter)
_USE_RE = re.compile(
    r'(?:app|router)\.use\s*\(\s*["\`\']([^"\'`\)]+)["\`\']\s*,\s*(\w+)',
)
# middleware on route: app.get('/path', authenticate, handler)
_MIDDLEWARE_RE = re.compile(
    r'(?:authenticate|requireAuth|isAuth|verifyToken|passport\.authenticate|ensureAuthenticated|jwtMiddleware|authMiddleware)',
    re.IGNORECASE,
)
# Colon-style path params: /users/:id/orders/:orderId
_COLON_PARAM_RE = re.compile(r':(\w+)')


class ExpressScanner(BaseScanner):
    def scan(self, project: Path) -> list[Route]:
        routes: list[Route] = []
        js_files = [
            f for f in project.rglob("*")
            if f.suffix in (".js", ".ts", ".mjs", ".cjs")
            and not any(p in str(f) for p in ("node_modules", "/dist/", "/.next/", "/build/", "spec.", ".test.", ".spec."))
        ]
        for filepath in js_files:
            try:
                text = filepath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            routes.extend(self._scan_file(filepath, text, project))
        return routes

    def _scan_file(self, filepath: Path, text: str, project: Path) -> list[Route]:
        routes: list[Route] = []
        lines = text.splitlines()
        rel = str(filepath.relative_to(project)).replace("\\", "/")

        for i, line in enumerate(lines):
            m = _ROUTE_RE.search(line)
            if not m:
                continue
            method = m.group(1).upper()
            path = m.group(2)
            path_params = _COLON_PARAM_RE.findall(path)

            # Check surrounding line for auth middleware
            context = "\n".join(lines[max(0, i-2) : min(i+5, len(lines))])
            auth = bool(_MIDDLEWARE_RE.search(context))
            role = self._infer_role(path, middlewares=[context])

            routes.append(Route(
                path=path,
                method=method,
                auth_required=auth,
                role=role,
                path_params=path_params,
                source_file=rel,
                source_line=i + 1,
                tags=["express"],
            ))
        return routes
