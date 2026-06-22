"""Framework-specific route scanners."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Route:
    path: str
    method: str                       # GET POST PUT PATCH DELETE
    auth_required: bool = False
    role: str = "customer"            # customer | admin | superadmin
    path_params: list[str] = field(default_factory=list)
    query_params: list[str] = field(default_factory=list)
    body_fields: list[str] = field(default_factory=list)
    handler_name: str = ""
    source_file: str = ""
    source_line: int = 0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "method": self.method,
            "authRequired": self.auth_required,
            "role": self.role,
            "pathParams": self.path_params,
            "queryParams": self.query_params,
            "bodyFields": self.body_fields,
            "handlerName": self.handler_name,
            "source": f"{self.source_file}:{self.source_line}" if self.source_line else self.source_file,
            "tags": self.tags,
        }


class BaseScanner:
    def scan(self, project: Path) -> list[Route]:
        raise NotImplementedError

    @staticmethod
    def _infer_role(path: str, handler: str = "", middlewares: list[str] | None = None) -> str:
        combined = f"{path} {handler} {' '.join(middlewares or [])}".lower()
        if any(k in combined for k in ("/superadmin", "superadmin", "super_admin")):
            return "superadmin"
        if any(k in combined for k in ("/admin", "admin", "is_admin", "require_admin", "admin_required")):
            return "admin"
        return "customer"

    @staticmethod
    def _infer_auth(path: str, handler: str = "", decorators: list[str] | None = None) -> bool:
        combined = f"{path} {handler} {' '.join(decorators or [])}".lower()
        auth_keywords = (
            "login_required", "authenticate", "requireauth", "isauth",
            "get_current_user", "jwt_required", "token_required",
            "verify_token", "auth_required", "protected", "authorized",
            "passport.authenticate", "ensure_authenticated",
        )
        return any(k in combined for k in auth_keywords)

    @staticmethod
    def _extract_path_params(path: str) -> list[str]:
        """Extract {param} and :param style path parameters."""
        import re
        curly = re.findall(r'\{(\w+)\}', path)
        colon = re.findall(r':(\w+)', path)
        return list(dict.fromkeys(curly + colon))
