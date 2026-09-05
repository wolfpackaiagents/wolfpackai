"""AMP authentication.

Ingestion/Public API: validates `X-API-Key` (public:secret) and resolves it to a
project_id (multi-tenancy, langfuse-style). Admin: `X-Admin-Key`.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Callable, Tuple

import httpx
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_db
from ..models.entities import ApiKey

ROLE_LEVELS = {"read_only": 0, "editor": 1, "admin": 2}


@dataclass(frozen=True)
class AuthContext:
    project_id: str
    db: Session
    role: str
    api_key_id: str

    def __iter__(self):
        yield self.project_id
        yield self.db


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def generate_api_key() -> Tuple[str, str, str]:
    """Returns (public_key, full_secret_key, hashed_secret)."""
    secret = secrets.token_hex(24)
    public = "pk-wp-" + secrets.token_hex(16)
    return public, secret, hash_secret(secret)


def resolve_project_id(
    request: Request,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> AuthContext:
    admin_key = get_settings().admin_api_key
    if x_api_key == admin_key:
        # admin-only mode: requires the X-Wolfpack-Project-Id header
        project = request.headers.get("X-Wolfpack-Project-Id")
        if not project:
            raise HTTPException(status_code=401, detail="Admin key requiere X-Wolfpack-Project-Id")
        _enforce_rate_limit(request, "admin")
        return AuthContext(project, db, "admin", "admin")
    public_key, _, provided_secret = x_api_key.partition(":")
    # also support the whole "public:secret" key
    if ":" in x_api_key:
        provided_secret = x_api_key.split(":", 1)[1]
    key_record = db.query(ApiKey).filter(ApiKey.public_key == public_key).filter(ApiKey.status == "active").first()
    if not key_record:
        raise HTTPException(status_code=401, detail="API key inválida")
    if not secrets.compare_digest(key_record.hashed_secret_key, hash_secret(provided_secret.strip())):
        raise HTTPException(status_code=401, detail="API key inválida")
    _enforce_rate_limit(request, key_record.id)
    return AuthContext(key_record.project_id, db, key_record.role, key_record.id)


def _enforce_rate_limit(request: Request, api_key_id: str) -> None:
    allowed, retry_after = request.app.state.rate_limiter.check(api_key_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )


def require_role(required_role: str) -> Callable:
    """Returns a dependency that rejects keys below the required role."""
    required_level = ROLE_LEVELS[required_role]

    def dependency(auth: AuthContext = Depends(resolve_project_id)) -> AuthContext:
        if ROLE_LEVELS.get(auth.role, -1) < required_level:
            raise HTTPException(status_code=403, detail="Insufficient API key permissions")
        return auth

    return dependency


def require_admin(x_admin_key: str = Header(None, alias="X-Admin-Key")):
    if x_admin_key != get_settings().admin_api_key:
        raise HTTPException(status_code=401, detail="Admin key inválida")
