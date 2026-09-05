"""Project-scoped metadata APIs for encrypted provider credentials."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.auth import AuthContext, require_role
from ..models.entities import ChannelConnection, ProviderSecret, ProviderSecretAudit
from ..services.provider_secrets import encrypt_provider_secret

router = APIRouter(prefix="/api/public/provider-secrets", tags=["provider-secrets"])
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


class ProviderSecretInput(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=16_384)
    rotation_interval_days: int | None = Field(default=None, ge=1, le=3660)
    expires_at: datetime | None = None


class ProviderSecretUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    value: str | None = Field(default=None, min_length=1, max_length=16_384)
    rotation_interval_days: int | None = Field(default=None, ge=1, le=3660)
    expires_at: datetime | None = None


def _validate_identifiers(provider: str, name: str) -> None:
    if not IDENTIFIER.fullmatch(provider) or not IDENTIFIER.fullmatch(name):
        raise HTTPException(status_code=422, detail="Provider and name must be lowercase identifiers")


def _out(secret: ProviderSecret) -> dict:
    return {
        "id": secret.id, "provider": secret.provider, "name": secret.name,
        "value_masked": "********", "version": secret.version,
        "rotation_interval_days": secret.rotation_interval_days, "expires_at": secret.expires_at,
        "last_rotated_at": secret.last_rotated_at, "created_at": secret.created_at,
        "updated_at": secret.updated_at,
    }


def _audit(auth: AuthContext, secret: ProviderSecret, action: str) -> None:
    auth.db.add(ProviderSecretAudit(
        project_id=auth.project_id, provider_secret_id=secret.id, action=action,
        actor_api_key_id=auth.api_key_id if auth.api_key_id != "admin" else None,
        details={"provider": secret.provider, "name": secret.name, "version": secret.version},
    ))


@router.get("")
def list_provider_secrets(auth: AuthContext = Depends(require_role("editor"))):
    return [_out(row) for row in auth.db.query(ProviderSecret).filter_by(project_id=auth.project_id).order_by(ProviderSecret.provider, ProviderSecret.name)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_provider_secret(payload: ProviderSecretInput, auth: AuthContext = Depends(require_role("editor"))):
    _validate_identifiers(payload.provider, payload.name)
    secret = ProviderSecret(id=uuid.uuid4().hex, project_id=auth.project_id, provider=payload.provider, name=payload.name, rotation_interval_days=payload.rotation_interval_days, expires_at=payload.expires_at)
    encrypt_provider_secret(secret, payload.value)
    auth.db.add(secret)
    _audit(auth, secret, "created")
    try:
        auth.db.commit()
    except Exception:
        auth.db.rollback()
        raise HTTPException(status_code=409, detail="A secret with this provider and name already exists")
    return _out(secret)


@router.get("/{secret_id}")
def get_provider_secret(secret_id: str, auth: AuthContext = Depends(require_role("editor"))):
    secret = auth.db.query(ProviderSecret).filter_by(id=secret_id, project_id=auth.project_id).first()
    if not secret:
        raise HTTPException(status_code=404, detail="Provider secret not found")
    return _out(secret)


@router.patch("/{secret_id}")
def update_provider_secret(secret_id: str, payload: ProviderSecretUpdate, auth: AuthContext = Depends(require_role("editor"))):
    secret = auth.db.query(ProviderSecret).filter_by(id=secret_id, project_id=auth.project_id).first()
    if not secret:
        raise HTTPException(status_code=404, detail="Provider secret not found")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        _validate_identifiers(secret.provider, changes["name"])
        secret.name = changes.pop("name")
    value = changes.pop("value", None)
    for field, item in changes.items():
        setattr(secret, field, item)
    if value is not None:
        secret.version += 1
        encrypt_provider_secret(secret, value)
    _audit(auth, secret, "rotated" if value is not None else "updated")
    try:
        auth.db.commit()
    except Exception:
        auth.db.rollback()
        raise HTTPException(status_code=409, detail="A secret with this provider and name already exists")
    return _out(secret)


@router.delete("/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_secret(secret_id: str, auth: AuthContext = Depends(require_role("editor"))):
    secret = auth.db.query(ProviderSecret).filter_by(id=secret_id, project_id=auth.project_id).first()
    if not secret:
        raise HTTPException(status_code=404, detail="Provider secret not found")
    connections = auth.db.query(ChannelConnection).filter_by(project_id=auth.project_id).all()
    if any(secret.id in (connection.secret_refs or {}).values() for connection in connections):
        raise HTTPException(status_code=409, detail="Provider secret is referenced by a channel connection")
    _audit(auth, secret, "deleted")
    auth.db.delete(secret)
    auth.db.commit()


@router.get("/{secret_id}/audit")
def list_provider_secret_audit(secret_id: str, auth: AuthContext = Depends(require_role("admin"))):
    exists = auth.db.query(ProviderSecret).filter_by(id=secret_id, project_id=auth.project_id).first()
    audited = auth.db.query(ProviderSecretAudit).filter_by(provider_secret_id=secret_id, project_id=auth.project_id).first()
    if not exists and not audited:
        raise HTTPException(status_code=404, detail="Provider secret not found")
    rows = auth.db.query(ProviderSecretAudit).filter_by(project_id=auth.project_id, provider_secret_id=secret_id).order_by(ProviderSecretAudit.created_at.desc())
    return [{"id": row.id, "action": row.action, "details": row.details, "created_at": row.created_at} for row in rows]
