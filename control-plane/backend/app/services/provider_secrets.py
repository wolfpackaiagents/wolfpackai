"""Envelope encryption primitives for provider credentials.

The master Fernet key encrypts a randomly generated per-secret data key. The
data key encrypts a context-bound payload, so a ciphertext cannot be replayed
into another project or secret row.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from ..core.config import get_settings
from ..models.entities import ProviderSecret


def _master_fernet() -> Fernet:
    key = get_settings().provider_secrets_master_key.encode()
    if not key:
        raise HTTPException(status_code=503, detail="Provider secret storage is not configured")
    try:
        return Fernet(key)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Provider secret storage is not configured") from exc


def encrypt_provider_secret(secret: ProviderSecret, value: str) -> None:
    data_key = Fernet.generate_key()
    payload = json.dumps(
        {"project_id": secret.project_id, "secret_id": secret.id, "value": value},
        separators=(",", ":"),
    ).encode()
    secret.encrypted_data_key = _master_fernet().encrypt(data_key).decode()
    secret.ciphertext = Fernet(data_key).encrypt(payload).decode()
    secret.last_rotated_at = datetime.now(timezone.utc)


def decrypt_provider_secret(secret: ProviderSecret) -> str:
    """Internal-only credential recovery for a provider runtime; never use in HTTP output."""
    try:
        data_key = _master_fernet().decrypt(secret.encrypted_data_key.encode())
        payload = json.loads(Fernet(data_key).decrypt(secret.ciphertext.encode()))
    except (InvalidToken, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("Provider secret cannot be decrypted") from exc
    if payload.get("project_id") != secret.project_id or payload.get("secret_id") != secret.id:
        raise RuntimeError("Provider secret envelope context mismatch")
    return payload["value"]
