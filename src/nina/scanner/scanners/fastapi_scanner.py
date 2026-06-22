"""FastAPI route scanner — extracts routes from @app.get/@router.post decorators."""
from __future__ import annotations

import re
from pathlib import Path

from . import BaseScanner, Route

# Matches: @app.get("/path"), @router.post("/path/{id}"), @app.delete(...)
_ROUTE_RE = re.compile(
    r'@\w+\.(get|post|put|patch|delete|head|options)\s*\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
# Matches async def / def after a route decorator
_HANDLER_RE = re.compile(r'(?:async\s+)?def\s+(\w+)\s*\(')
# Detects auth dependencies inline
_AUTH_DEP_RE = re.compile(
    r'Depends\s*\(\s*(\w+)\s*\)|current_user\s*:|get_current_user|oauth2_scheme',
    re.IGNORECASE,
)
# Pydantic body param: body: SomeModel, data: CreateUserRequest, etc.
_BODY_RE = re.compile(r'(\w+)\s*:\s*([A-Z]\w+(?:Request|Schema|Body|In|Create|Update))\b')
# Query param: q: str = Query(...), limit: int = Query(...)
_QUERY_RE = re.compile(r'(\w+)\s*(?::\s*\w+)?\s*=\s*Query\s*\(')
# Router prefix: router = APIRouter(prefix="/v1/products")
_PREFIX_RE = re.compile(r'APIRouter\s*\(.*?prefix\s*=\s*["\']([^"\']*)["\']', re.DOTALL)


class FastAPIScanner(BaseScanner):
    def scan(self, project: Path) -> list[Route]:
        routes: list[Route] = []
        py_files = [
            f for f in project.rglob("*.py")
            if not any(p in str(f) for p in ("/.venv/", "/venv/", "/site-packages/", "/__pycache__/", "/test"))
        ]
        for filepath in py_files:
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

        # Detect router prefix for this file
        prefix_match = _PREFIX_RE.search(text)
        prefix = prefix_match.group(1) if prefix_match else ""

        i = 0
        while i < len(lines):
            line = lines[i]
            m = _ROUTE_RE.search(line)
            if m:
                method = m.group(1).upper()
                path = prefix + m.group(2)
                path_params = self._extract_path_params(path)

                # Scan the next ~20 lines to find handler signature and dependencies
                window = "\n".join(lines[i : min(i + 20, len(lines))])
                handler_m = _HANDLER_RE.search(window)
                handler_name = handler_m.group(1) if handler_m else ""

                auth = bool(_AUTH_DEP_RE.search(window))
                role = self._infer_role(path, handler_name)
                if role == "customer" and auth:
                    pass  # auth_required stays True

                query_params = _QUERY_RE.findall(window)
                body_m = _BODY_RE.search(window)
                body_fields: list[str] = [body_m.group(1)] if body_m else []

                routes.append(Route(
                    path=path,
                    method=method,
                    auth_required=auth,
                    role=role,
                    path_params=path_params,
                    query_params=list(query_params),
                    body_fields=body_fields,
                    handler_name=handler_name,
                    source_file=rel,
                    source_line=i + 1,
                    tags=["fastapi"],
                ))
            i += 1
        return routes
