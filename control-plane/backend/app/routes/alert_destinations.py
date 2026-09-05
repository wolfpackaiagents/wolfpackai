"""Project-scoped alert notification destination CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.auth import AuthContext, require_role
from ..models.entities import AlertDestination
from ..services.alert_notifier import notify

router = APIRouter(prefix="/api/public/alert-destinations", tags=["alert-destinations"])


class DestinationInput(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    destination_type: Literal["slack_webhook", "discord_webhook", "smtp"]
    config: dict[str, Any] = Field(min_length=1)
    enabled: bool = True


class DestinationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    config: dict[str, Any] | None = None
    enabled: bool | None = None


def _out(dest: AlertDestination) -> dict[str, Any]:
    return {
        "id": dest.id,
        "name": dest.name,
        "destination_type": dest.destination_type,
        "config": dest.config,
        "enabled": dest.enabled,
        "last_notified_at": dest.last_notified_at.isoformat() if dest.last_notified_at else None,
        "last_error": dest.last_error,
        "created_at": dest.created_at.isoformat() if dest.created_at else None,
        "updated_at": dest.updated_at.isoformat() if dest.updated_at else None,
    }


@router.get("")
def list_destinations(auth: AuthContext = Depends(require_role("read_only"))):
    return [_out(row) for row in auth.db.query(AlertDestination).filter_by(project_id=auth.project_id).order_by(AlertDestination.name).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_destination(body: DestinationInput, auth: AuthContext = Depends(require_role("editor"))):
    existing = auth.db.query(AlertDestination).filter_by(project_id=auth.project_id, name=body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Destination name already exists")
    dest = AlertDestination(id=uuid.uuid4().hex, project_id=auth.project_id, **body.model_dump())
    auth.db.add(dest)
    auth.db.commit()
    auth.db.refresh(dest)
    return _out(dest)


@router.patch("/{destination_id}")
def update_destination(destination_id: str, body: DestinationUpdate, auth: AuthContext = Depends(require_role("editor"))):
    dest = auth.db.query(AlertDestination).filter_by(id=destination_id, project_id=auth.project_id).first()
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found")
    changes = body.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] != dest.name:
        duplicate = auth.db.query(AlertDestination).filter_by(project_id=auth.project_id, name=changes["name"]).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Destination name already exists")
    for field, value in changes.items():
        setattr(dest, field, value)
    dest.updated_at = datetime.now(timezone.utc)
    auth.db.commit()
    auth.db.refresh(dest)
    return _out(dest)


@router.delete("/{destination_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_destination(destination_id: str, auth: AuthContext = Depends(require_role("editor"))):
    dest = auth.db.query(AlertDestination).filter_by(id=destination_id, project_id=auth.project_id).first()
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found")
    auth.db.delete(dest)
    auth.db.commit()


@router.post("/{destination_id}/test", status_code=status.HTTP_200_OK)
def test_destination(destination_id: str, auth: AuthContext = Depends(require_role("editor"))):
    """Send a test alert to verify the destination configuration."""
    from ..models.entities import Alert

    dest = auth.db.query(AlertDestination).filter_by(id=destination_id, project_id=auth.project_id).first()
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found")
    test_alert = Alert(
        id="test-" + uuid.uuid4().hex,
        project_id=auth.project_id,
        source="test",
        event_type="test_notification",
        severity="warning",
        message="This is a test alert from Wolfpack AMP. If you received this, the destination is configured correctly.",
    )
    results = notify(test_alert, [dest])

    outcomes = []
    for r in results:
        dest.last_error = r.get("error")
        if r["success"]:
            dest.last_notified_at = datetime.now(timezone.utc)
        outcomes.append(r)
    auth.db.commit()
    if not outcomes:
        raise HTTPException(status_code=500, detail="No notification dispatcher matched")
    first = outcomes[0]
    if not first["success"]:
        raise HTTPException(status_code=502, detail=first["error"])
    return {"success": True, "destination_id": destination_id, "message": "Test notification sent successfully."}