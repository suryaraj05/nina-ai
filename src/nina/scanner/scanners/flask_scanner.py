"""Flask route scanner — extracts from @app.route and Blueprint decorators."""
from __future__ import annotations

import re
from pathlib import Path

from . import BaseScanner, Route

# @app.route("/path", methods=["GET", "POST"])
_ROUTE_RE = re.compile(
    r'@(?:app|bp|blueprint|\w+)\.route\s*\(\s*["\']([^"\']+)["\'](?:[^)]*methods\s*=\s*\[([^\]]+)\])?',
    re.IGNORECASE,
)
# @app.get("/path") — Flask 2.x shorthand
_SHORTHAND_RE = re.compile(
    r'@(?:app|bp|blueprint|\w+)\.(get|post|put|patch|delete)\s*\(\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_AUTH_RE = re.compile(
    r'@login_required|@jwt_required|@token_required|login_required\(\)|verify_jwt_in_request',
    re.IGNORECASE,
)
_HANDLER_RE = re.compile(r'def\s+(\w+)\s*\(')


class FlaskScanner(BaseScanner):
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
            # Only process files that look like Flask apps
            if "@app.route" not in text and ".route(" not in text and "@app.get" not in text:
                continue
            routes.extend(self._scan_file(filepath, text, project))
        return routes

    def _scan_file(self, filepath: Path, text: str, project: Path) -> list[Route]:
        routes: list[Route] = []
        lines = text.splitlines()
        rel = str(filepath.relative_to(project)).replace("\\", "/")

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check Flask 2.x shorthand
            sh = _SHORTHAND_RE.search(line)
            if sh:
                method = sh.group(1).upper()
                path = sh.group(2)
                window = "\n".join(lines[i : min(i + 10, len(lines))])
                handler_m = _HANDLER_RE.search(window)
                auth = bool(_AUTH_RE.search("\n".join(lines[max(0, i-3): i+10])))
                routes.append(Route(
                    path=path,
                    method=method,
                    auth_required=auth,
                    role=self._infer_role(path, handler_m.group(1) if handler_m else ""),
                    path_params=self._extract_path_params(path),
                    handler_name=handler_m.group(1) if handler_m else "",
                    source_file=rel,
                    source_line=i + 1,
                    tags=["flask"],
                ))
                i += 1
                continue

            # @app.route() style
            m = _ROUTE_RE.search(line)
            if m:
                path = m.group(1)
                methods_raw = m.group(2) or '"GET"'
                methods = re.findall(r'"(\w+)"', methods_raw)
                if not methods:
                    methods = ["GET"]
                window = "\n".join(lines[i : min(i + 15, len(lines))])
                handler_m = _HANDLER_RE.search(window)
                auth = bool(_AUTH_RE.search("\n".join(lines[max(0, i-3): i+15])))
                handler_name = handler_m.group(1) if handler_m else ""
                for method in methods:
                    routes.append(Route(
                        path=path,
                        method=method.upper(),
                        auth_required=auth,
                        role=self._infer_role(path, handler_name),
                        path_params=self._extract_path_params(path),
                        handler_name=handler_name,
                        source_file=rel,
                        source_line=i + 1,
                        tags=["flask"],
                    ))
            i += 1
        return routes
