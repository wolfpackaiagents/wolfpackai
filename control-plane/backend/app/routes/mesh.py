"""Project-scoped Agentic Mesh registry and controlled environments."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func

from ..core.auth import AuthContext, require_role
from ..core.config import get_settings
from ..models.entities import ChatRun, Environment, EnvironmentRegistration, MeshDefinition, MeshInteraction, RegistrationHeartbeat, RuntimeReplica, Trace

router = APIRouter(prefix="/api/public/mesh", tags=["mesh"])


class EnvironmentInput(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    name: str = Field(min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=2000)
    labels: dict[str, str] = Field(default_factory=dict)


class DefinitionInput(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,126}$")
    kind: Literal["agent", "team", "workflow"]
    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=64)
    description: Optional[str] = Field(default=None, max_length=4000)
    summary: dict[str, Any] = Field(default_factory=dict)
    artifact_digest: Optional[str] = Field(default=None, max_length=128)
    policy_hash: Optional[str] = Field(default=None, max_length=128)


class RegistrationInput(BaseModel):
    environment_id: str
    definition_id: str
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    schedule_endpoint: Optional[str] = Field(default=None, max_length=2048)
    chat_endpoint: Optional[str] = Field(default=None, max_length=2048)


class EnvironmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=2000)
    labels: Optional[dict[str, str]] = None
    status: Optional[Literal["active", "inactive"]] = None


class RegistrationUpdate(BaseModel):
    enabled: Optional[bool] = None
    tags: Optional[list[str]] = None
    schedule_endpoint: Optional[str] = Field(default=None, max_length=2048)
    chat_endpoint: Optional[str] = Field(default=None, max_length=2048)


class HeartbeatInput(BaseModel):
    instance_id: str = Field(min_length=1, max_length=128)
    version: Optional[str] = Field(default=None, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReplicaInput(BaseModel):
    instance_id: str = Field(min_length=1, max_length=128)
    endpoint: str = Field(min_length=1, max_length=2048)
    capacity: int = Field(default=1, ge=1, le=10_000)
    enabled: bool = True


class ReplicaUpdate(BaseModel):
    endpoint: str | None = Field(default=None, min_length=1, max_length=2048)
    capacity: int | None = Field(default=None, ge=1, le=10_000)
    enabled: bool | None = None


class InteractionInput(BaseModel):
    source: str = Field(min_length=1, max_length=255)
    target: str = Field(min_length=1, max_length=255)
    source_display_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    target_display_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    interaction_type: Literal["delegation", "handoff", "route", "broadcast", "task", "tool"] = "delegation"
    operation: Optional[str] = Field(default=None, min_length=1, max_length=255)
    tool_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    trace_id: Optional[str] = Field(default=None, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _environment_out(environment: Environment) -> dict[str, Any]:
    return {
        "id": environment.id,
        "slug": environment.slug,
        "name": environment.name,
        "description": environment.description,
        "status": environment.status,
        "labels": environment.labels or {},
        "created_at": environment.created_at,
        "updated_at": environment.updated_at,
    }


def _definition_out(definition: MeshDefinition) -> dict[str, Any]:
    return {
        "id": definition.id,
        "key": definition.key,
        "kind": definition.kind,
        "name": definition.name,
        "version": definition.version,
        "description": definition.description,
        "summary": definition.summary or {},
        "artifact_digest": definition.artifact_digest,
        "policy_hash": definition.policy_hash,
        "created_at": definition.created_at,
    }


def _registration_out(registration: EnvironmentRegistration, environment: Environment, definition: MeshDefinition, heartbeats: list[RegistrationHeartbeat] | None = None) -> dict[str, Any]:
    heartbeats = heartbeats or []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=get_settings().mesh_heartbeat_ttl_seconds)
    def as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    online_replicas = sum(as_utc(heartbeat.last_seen) >= cutoff for heartbeat in heartbeats)
    last_seen_at = max((as_utc(heartbeat.last_seen) for heartbeat in heartbeats), default=None)
    if not heartbeats:
        health_status = "unknown"
    elif online_replicas == 0:
        health_status = "offline"
    elif online_replicas < len(heartbeats):
        health_status = "degraded"
    else:
        health_status = "online"
    return {
        "id": registration.id,
        "environment_id": environment.id,
        "environment_slug": environment.slug,
        "definition_id": definition.id,
        "definition_key": definition.key,
        "definition_kind": definition.kind,
        "definition_name": definition.name,
        "definition_version": definition.version,
        "enabled": registration.enabled,
        "online_replicas": online_replicas,
        "last_seen_at": last_seen_at,
        "health_status": health_status,
        "tags": registration.tags or [],
        "schedule_endpoint": registration.schedule_endpoint,
        "chat_endpoint": registration.chat_endpoint,
        "created_at": registration.created_at,
        "updated_at": registration.updated_at,
    }


def _interaction_out(interaction: MeshInteraction) -> dict[str, Any]:
    return {"id": interaction.id, "source": interaction.source, "target": interaction.target, "source_display_name": interaction.source_display_name, "target_display_name": interaction.target_display_name, "interaction_type": interaction.interaction_type, "operation": interaction.operation, "tool_name": interaction.tool_name, "trace_id": interaction.trace_id, "metadata": interaction.metadata_field or {}, "created_at": interaction.created_at}


@router.get("/catalog")
def catalog(environment_id: Optional[str] = None, registration_id: Optional[str] = None, auth: AuthContext = Depends(require_role("read_only"))):
    environments_query = auth.db.query(Environment).filter(Environment.project_id == auth.project_id)
    registrations_query = auth.db.query(EnvironmentRegistration).filter(EnvironmentRegistration.project_id == auth.project_id)
    if environment_id:
        environments_query = environments_query.filter(Environment.id == environment_id)
        registrations_query = registrations_query.filter(EnvironmentRegistration.environment_id == environment_id)
    if registration_id:
        registrations_query = registrations_query.filter(EnvironmentRegistration.id == registration_id)
    registrations = registrations_query.all()
    heartbeat_rows = auth.db.query(RegistrationHeartbeat).filter(
        RegistrationHeartbeat.project_id == auth.project_id,
        RegistrationHeartbeat.registration_id.in_([registration.id for registration in registrations]),
    ).all() if registrations else []
    heartbeats_by_registration: dict[str, list[RegistrationHeartbeat]] = {}
    for heartbeat in heartbeat_rows:
        heartbeats_by_registration.setdefault(heartbeat.registration_id, []).append(heartbeat)
    registration_definition_ids = [registration.definition_id for registration in registrations]
    if registration_id:
        environments_query = environments_query.filter(Environment.id.in_([registration.environment_id for registration in registrations]))
    environments = environments_query.order_by(Environment.name).all()
    definitions_query = auth.db.query(MeshDefinition).filter(MeshDefinition.project_id == auth.project_id)
    if environment_id or registration_id:
        definitions_query = definitions_query.filter(MeshDefinition.id.in_(registration_definition_ids))
    definitions = definitions_query.order_by(MeshDefinition.name, MeshDefinition.version.desc()).all()
    environments_by_id = {environment.id: environment for environment in environments}
    definitions_by_id = {definition.id: definition for definition in definitions}
    registrations_by_environment: dict[str, list[dict[str, Any]]] = {environment.id: [] for environment in environments}
    for registration in registrations:
        environment = environments_by_id.get(registration.environment_id)
        definition = definitions_by_id.get(registration.definition_id)
        if environment and definition:
            registrations_by_environment[environment.id].append(_registration_out(registration, environment, definition, heartbeats_by_registration.get(registration.id)))
    return {
        "summary": {
            "environments": len(environments),
            "registrations": len(registrations),
            "active_registrations": sum(registration.enabled for registration in registrations),
        },
        "environments": [{**_environment_out(environment), "registrations": registrations_by_environment[environment.id]} for environment in environments],
        "definitions": [_definition_out(definition) for definition in definitions],
    }


@router.post("/environments", status_code=status.HTTP_201_CREATED)
def create_environment(body: EnvironmentInput, auth: AuthContext = Depends(require_role("editor"))):
    if auth.db.query(Environment).filter(Environment.project_id == auth.project_id, Environment.slug == body.slug).first():
        raise HTTPException(status_code=409, detail="Environment slug already exists")
    environment = Environment(project_id=auth.project_id, **body.model_dump())
    auth.db.add(environment)
    auth.db.commit()
    auth.db.refresh(environment)
    return _environment_out(environment)


@router.patch("/environments/{environment_id}")
def update_environment(environment_id: str, body: EnvironmentUpdate, auth: AuthContext = Depends(require_role("editor"))):
    environment = auth.db.query(Environment).filter(Environment.id == environment_id, Environment.project_id == auth.project_id).first()
    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(environment, field, value)
    auth.db.commit()
    auth.db.refresh(environment)
    return _environment_out(environment)


@router.delete("/environments/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_environment(environment_id: str, auth: AuthContext = Depends(require_role("editor"))):
    environment = auth.db.query(Environment).filter(Environment.id == environment_id, Environment.project_id == auth.project_id).first()
    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")
    registration_count = auth.db.query(EnvironmentRegistration).filter(EnvironmentRegistration.project_id == auth.project_id, EnvironmentRegistration.environment_id == environment_id).count()
    trace_count = auth.db.query(Trace).filter(Trace.project_id == auth.project_id, Trace.environment_id == environment_id).count()
    if registration_count or trace_count:
        references = []
        if registration_count:
            references.append(f"{registration_count} registration(s)")
        if trace_count:
            references.append(f"{trace_count} trace(s)")
        raise HTTPException(status_code=409, detail=f"Environment cannot be deleted while referenced by {', '.join(references)}")
    auth.db.delete(environment)
    auth.db.commit()


@router.post("/definitions", status_code=status.HTTP_201_CREATED)
def create_definition(body: DefinitionInput, auth: AuthContext = Depends(require_role("editor"))):
    existing = auth.db.query(MeshDefinition).filter(
        MeshDefinition.project_id == auth.project_id, MeshDefinition.key == body.key, MeshDefinition.version == body.version
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Definition version already exists")
    definition = MeshDefinition(project_id=auth.project_id, **body.model_dump())
    auth.db.add(definition)
    auth.db.commit()
    auth.db.refresh(definition)
    return _definition_out(definition)


@router.post("/registrations", status_code=status.HTTP_201_CREATED)
def create_registration(body: RegistrationInput, auth: AuthContext = Depends(require_role("editor"))):
    environment = auth.db.query(Environment).filter(Environment.id == body.environment_id, Environment.project_id == auth.project_id).first()
    definition = auth.db.query(MeshDefinition).filter(MeshDefinition.id == body.definition_id, MeshDefinition.project_id == auth.project_id).first()
    if not environment or not definition:
        raise HTTPException(status_code=404, detail="Environment or definition not found")
    if environment.status != "active":
        raise HTTPException(status_code=409, detail="Environment is not active")
    if auth.db.query(EnvironmentRegistration).filter(EnvironmentRegistration.environment_id == environment.id, EnvironmentRegistration.definition_id == definition.id).first():
        raise HTTPException(status_code=409, detail="Definition is already registered in this environment")
    registration = EnvironmentRegistration(project_id=auth.project_id, **body.model_dump())
    auth.db.add(registration)
    auth.db.commit()
    auth.db.refresh(registration)
    return _registration_out(registration, environment, definition)


@router.patch("/registrations/{registration_id}")
def update_registration(registration_id: str, body: RegistrationUpdate, auth: AuthContext = Depends(require_role("editor"))):
    registration = auth.db.query(EnvironmentRegistration).filter(EnvironmentRegistration.id == registration_id, EnvironmentRegistration.project_id == auth.project_id).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    environment = auth.db.query(Environment).filter(Environment.id == registration.environment_id, Environment.project_id == auth.project_id).first()
    definition = auth.db.query(MeshDefinition).filter(MeshDefinition.id == registration.definition_id, MeshDefinition.project_id == auth.project_id).first()
    if not environment or not definition:
        raise HTTPException(status_code=409, detail="Registration references an unavailable environment or definition")
    updates = body.model_dump(exclude_unset=True)
    if updates.get("enabled") and environment.status != "active":
        raise HTTPException(status_code=409, detail="Environment is not active")
    for field, value in updates.items():
        setattr(registration, field, value)
    auth.db.commit()
    auth.db.refresh(registration)
    return _registration_out(registration, environment, definition)


@router.post("/registrations/{registration_id}/heartbeat")
def heartbeat(registration_id: str, body: HeartbeatInput, auth: AuthContext = Depends(require_role("editor"))):
    registration = auth.db.query(EnvironmentRegistration).filter(
        EnvironmentRegistration.id == registration_id,
        EnvironmentRegistration.project_id == auth.project_id,
    ).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    record = auth.db.query(RegistrationHeartbeat).filter(
        RegistrationHeartbeat.registration_id == registration.id,
        RegistrationHeartbeat.instance_id == body.instance_id,
    ).first()
    if record is None:
        record = RegistrationHeartbeat(project_id=auth.project_id, registration_id=registration.id, instance_id=body.instance_id, version=body.version, metadata_field=body.metadata)
        auth.db.add(record)
    else:
        record.version = body.version
        record.metadata_field = body.metadata
        record.last_seen = datetime.now(timezone.utc)
    auth.db.commit()
    auth.db.refresh(record)
    return {"registration_id": registration.id, "instance_id": record.instance_id, "last_seen_at": record.last_seen}


def _replica_out(replica: RuntimeReplica) -> dict[str, Any]:
    return {"id": replica.id, "registration_id": replica.registration_id, "instance_id": replica.instance_id, "endpoint": replica.endpoint, "capacity": replica.capacity, "enabled": replica.enabled, "created_at": replica.created_at, "updated_at": replica.updated_at}


@router.get("/registrations/{registration_id}/replicas")
def list_replicas(registration_id: str, auth: AuthContext = Depends(require_role("admin"))):
    _registration = auth.db.query(EnvironmentRegistration).filter_by(id=registration_id, project_id=auth.project_id).first()
    if not _registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    return [_replica_out(item) for item in auth.db.query(RuntimeReplica).filter_by(registration_id=registration_id, project_id=auth.project_id).order_by(RuntimeReplica.instance_id).all()]


@router.post("/registrations/{registration_id}/replicas", status_code=status.HTTP_201_CREATED)
def register_replica(registration_id: str, body: ReplicaInput, auth: AuthContext = Depends(require_role("admin"))):
    registration = auth.db.query(EnvironmentRegistration).filter_by(id=registration_id, project_id=auth.project_id).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    if auth.db.query(RuntimeReplica).filter_by(registration_id=registration_id, instance_id=body.instance_id).first():
        raise HTTPException(status_code=409, detail="Replica already exists")
    replica = RuntimeReplica(project_id=auth.project_id, registration_id=registration_id, **body.model_dump())
    auth.db.add(replica)
    auth.db.commit()
    auth.db.refresh(replica)
    return _replica_out(replica)


@router.patch("/registrations/{registration_id}/replicas/{instance_id}")
def update_replica(registration_id: str, instance_id: str, body: ReplicaUpdate, auth: AuthContext = Depends(require_role("admin"))):
    replica = auth.db.query(RuntimeReplica).filter_by(registration_id=registration_id, instance_id=instance_id, project_id=auth.project_id).first()
    if not replica:
        raise HTTPException(status_code=404, detail="Replica not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(replica, field, value)
    auth.db.commit()
    auth.db.refresh(replica)
    return _replica_out(replica)


@router.delete("/registrations/{registration_id}/replicas/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_replica(registration_id: str, instance_id: str, auth: AuthContext = Depends(require_role("admin"))):
    replica = auth.db.query(RuntimeReplica).filter_by(registration_id=registration_id, instance_id=instance_id, project_id=auth.project_id).first()
    if not replica:
        raise HTTPException(status_code=404, detail="Replica not found")
    auth.db.delete(replica)
    auth.db.commit()


@router.delete("/registrations/{registration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_registration(registration_id: str, auth: AuthContext = Depends(require_role("editor"))):
    registration = auth.db.query(EnvironmentRegistration).filter(EnvironmentRegistration.id == registration_id, EnvironmentRegistration.project_id == auth.project_id).first()
    if not registration:
        raise HTTPException(status_code=404, detail="Registration not found")
    chat_run_count = auth.db.query(ChatRun).filter(ChatRun.project_id == auth.project_id, ChatRun.registration_id == registration_id).count()
    trace_count = auth.db.query(Trace).filter(Trace.project_id == auth.project_id, Trace.registration_id == registration_id).count()
    if chat_run_count or trace_count:
        references = []
        if chat_run_count:
            references.append(f"{chat_run_count} chat run(s)")
        if trace_count:
            references.append(f"{trace_count} trace(s)")
        raise HTTPException(status_code=409, detail=f"Registration cannot be deleted while referenced by {', '.join(references)}")
    auth.db.delete(registration)
    auth.db.commit()


@router.post("/interactions", status_code=status.HTTP_201_CREATED)
def create_interaction(body: InteractionInput, auth: AuthContext = Depends(require_role("editor"))):
    values = body.model_dump(exclude={"metadata"})
    interaction = MeshInteraction(project_id=auth.project_id, **values, metadata_field=body.metadata)
    auth.db.add(interaction)
    auth.db.commit()
    auth.db.refresh(interaction)
    return _interaction_out(interaction)


@router.get("/interactions")
def list_interactions(trace_id: Optional[str] = None, environment_id: Optional[str] = None, registration_id: Optional[str] = None, from_: Optional[datetime] = Query(default=None, alias="from"), to: Optional[datetime] = None, limit: int = 100, auth: AuthContext = Depends(require_role("read_only"))):
    query = auth.db.query(MeshInteraction).filter(MeshInteraction.project_id == auth.project_id)
    if trace_id:
        query = query.filter(MeshInteraction.trace_id == trace_id)
    if environment_id or registration_id:
        query = query.join(Trace, Trace.id == MeshInteraction.trace_id).filter(Trace.project_id == auth.project_id)
        if environment_id:
            query = query.filter(Trace.environment_id == environment_id)
        if registration_id:
            query = query.filter(Trace.registration_id == registration_id)
    if from_:
        query = query.filter(MeshInteraction.created_at >= from_)
    if to:
        query = query.filter(MeshInteraction.created_at <= to)
    return [_interaction_out(item) for item in query.order_by(MeshInteraction.created_at.desc()).limit(min(limit, 500)).all()]


@router.get("/graph")
def graph(environment_id: Optional[str] = None, registration_id: Optional[str] = None, from_: Optional[datetime] = Query(default=None, alias="from"), to: Optional[datetime] = None, auth: AuthContext = Depends(require_role("read_only"))):
    query = auth.db.query(MeshInteraction.source, MeshInteraction.target, MeshInteraction.source_display_name, MeshInteraction.target_display_name, MeshInteraction.interaction_type, MeshInteraction.operation, MeshInteraction.tool_name, func.count(MeshInteraction.id).label("count"), func.max(MeshInteraction.created_at).label("last_seen")).filter(MeshInteraction.project_id == auth.project_id)
    if environment_id or registration_id:
        query = query.join(Trace, Trace.id == MeshInteraction.trace_id).filter(Trace.project_id == auth.project_id)
        if environment_id:
            query = query.filter(Trace.environment_id == environment_id)
        if registration_id:
            query = query.filter(Trace.registration_id == registration_id)
    if from_:
        query = query.filter(MeshInteraction.created_at >= from_)
    if to:
        query = query.filter(MeshInteraction.created_at <= to)
    rows = query.group_by(MeshInteraction.source, MeshInteraction.target, MeshInteraction.source_display_name, MeshInteraction.target_display_name, MeshInteraction.interaction_type, MeshInteraction.operation, MeshInteraction.tool_name).all()
    labels = {row.source: row.source_display_name or row.source for row in rows}
    labels.update({row.target: row.target_display_name or row.target for row in rows})
    return {"nodes": [{"id": name, "label": labels[name]} for name in sorted(labels)], "edges": [{"source": row.source, "target": row.target, "source_display_name": row.source_display_name, "target_display_name": row.target_display_name, "interaction_type": row.interaction_type, "operation": row.operation, "tool_name": row.tool_name, "count": row.count, "last_seen": row.last_seen} for row in rows]}
