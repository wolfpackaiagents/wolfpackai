"""Domain model of the AMP: multi-tenancy, traces, observations and scores.

Design inspired by langfuse but simplified for the MVP: everything lives in Postgres
(phase 2 allows migrating to ClickHouse without touching the API). Each tenant table
carries `project_id`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from ..core.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(32), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_org_id", "organization_id"),)

    id = Column(String(32), primary_key=True, default=_uuid)
    organization_id = Column(String(32), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    retention_days = Column(Integer, default=30, nullable=False)
    governance_roles = Column(JSON, nullable=True)
    schedule_policy = Column(JSON, nullable=True)
    pii_redaction_config = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class Environment(Base):
    """A controlled deployment context for Mesh registrations."""

    __tablename__ = "environments"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", name="uq_environments_project_slug"),
        Index("ix_environments_project_status", "project_id", "status"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    slug = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="active", nullable=False)
    labels = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class MeshDefinition(Base):
    """A versioned, declarative agent, team, or workflow artifact."""

    __tablename__ = "mesh_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "key", "version", name="uq_mesh_definitions_project_key_version"),
        Index("ix_mesh_definitions_project_kind", "project_id", "kind"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    key = Column(String(128), nullable=False)
    kind = Column(String(20), nullable=False)
    name = Column(String(255), nullable=False)
    version = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    summary = Column(JSON, default=dict, nullable=False)
    artifact_digest = Column(String(128), nullable=True)
    policy_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class EnvironmentRegistration(Base):
    """The enabled state of a versioned definition in an environment."""

    __tablename__ = "environment_registrations"
    __table_args__ = (
        UniqueConstraint("environment_id", "definition_id", name="uq_environment_registrations_environment_definition"),
        Index("ix_environment_registrations_environment_enabled", "environment_id", "enabled"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    environment_id = Column(String(32), ForeignKey("environments.id"), nullable=False)
    definition_id = Column(String(32), ForeignKey("mesh_definitions.id"), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    schedule_endpoint = Column(String(2048), nullable=True)
    chat_endpoint = Column(String(2048), nullable=True)
    schedule_policy = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class RegistrationHeartbeat(Base):
    """Latest liveness assertion from one runtime replica of a registration."""

    __tablename__ = "registration_heartbeats"
    __table_args__ = (
        UniqueConstraint("registration_id", "instance_id", name="uq_registration_heartbeats_registration_instance"),
        Index("ix_registration_heartbeats_registration_seen", "registration_id", "last_seen"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    registration_id = Column(String(32), ForeignKey("environment_registrations.id"), nullable=False)
    instance_id = Column(String(128), nullable=False)
    version = Column(String(64), nullable=True)
    metadata_field = Column("metadata", JSON, default=dict, nullable=False)
    last_seen = Column(DateTime(timezone=True), default=_now, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class RuntimeReplica(Base):
    """An operator-authorized HTTP runtime replica for a registration."""

    __tablename__ = "runtime_replicas"
    __table_args__ = (
        UniqueConstraint("registration_id", "instance_id", name="uq_runtime_replicas_registration_instance"),
        Index("ix_runtime_replicas_registration_enabled", "registration_id", "enabled"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    registration_id = Column(String(32), ForeignKey("environment_registrations.id"), nullable=False)
    instance_id = Column(String(128), nullable=False)
    endpoint = Column(String(2048), nullable=False)
    capacity = Column(Integer, nullable=False, default=1)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class Schedule(Base):
    """A durable, project-scoped trigger for an enabled Mesh registration."""

    __tablename__ = "schedules"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_schedules_project_name"),
        Index("ix_schedules_project_status_next", "project_id", "status", "next_run_at"),
        Index("ix_schedules_registration", "registration_id"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    registration_id = Column(String(32), ForeignKey("environment_registrations.id"), nullable=False)
    name = Column(String(128), nullable=False)
    schedule_type = Column(String(16), nullable=False)
    timezone = Column(String(64), nullable=False, default="UTC")
    at = Column(DateTime(timezone=True), nullable=True)
    interval_seconds = Column(Integer, nullable=True)
    cron = Column(String(128), nullable=True)
    payload = Column(JSON, default=dict, nullable=False)
    status = Column(String(16), nullable=False, default="active")
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    max_attempts = Column(Integer, nullable=False, default=1)
    retry_delay_seconds = Column(Integer, nullable=False, default=60)
    misfire_policy = Column(String(16), nullable=False, default="skip")
    misfire_grace_seconds = Column(Integer, nullable=False, default=60)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)
    paused_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)


class ScheduledTaskRun(Base):
    """One idempotent execution attempt for a schedule occurrence."""

    __tablename__ = "scheduled_task_runs"
    __table_args__ = (
        UniqueConstraint("schedule_id", "occurrence_key", name="uq_scheduled_task_runs_schedule_occurrence"),
        Index("ix_scheduled_task_runs_project_status", "project_id", "status", "scheduled_for"),
        Index("ix_scheduled_task_runs_schedule_scheduled", "schedule_id", "scheduled_for"),
        Index("ix_scheduled_task_runs_claimable", "status", "retry_at", "lease_expires_at"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    schedule_id = Column(String(32), ForeignKey("schedules.id"), nullable=False)
    registration_id = Column(String(32), ForeignKey("environment_registrations.id"), nullable=False)
    occurrence_key = Column(String(160), nullable=False)
    trigger = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    scheduled_for = Column(DateTime(timezone=True), nullable=False)
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False)
    retry_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    fencing_token = Column(Integer, nullable=False, default=0)
    claimed_by = Column(String(128), nullable=True)
    deadline_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    result = Column(JSON, nullable=True)
    trace_id = Column(String(64), nullable=True)
    payload = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class MeshInteraction(Base):
    """A directed runtime handoff, delegation, or broadcast between Mesh members."""

    __tablename__ = "mesh_interactions"
    __table_args__ = (
        Index("ix_mesh_interactions_project_created", "project_id", "created_at"),
        Index("ix_mesh_interactions_project_edge", "project_id", "source", "target"),
        Index("ix_mesh_interactions_trace", "trace_id"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    trace_id = Column(String(64), ForeignKey("traces.id"), nullable=True)
    source = Column(String(255), nullable=False)
    target = Column(String(255), nullable=False)
    source_display_name = Column(String(255), nullable=True)
    target_display_name = Column(String(255), nullable=True)
    interaction_type = Column(String(32), nullable=False, default="delegation")
    operation = Column(String(255), nullable=True)
    tool_name = Column(String(255), nullable=True)
    metadata_field = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class ChatRun(Base):
    __tablename__ = "chat_runs"
    __table_args__ = (
        Index("ix_chat_runs_project_created", "project_id", "created_at"),
        Index("ix_chat_runs_conversation_created", "conversation_id", "created_at"),
        UniqueConstraint("conversation_id", "idempotency_key", name="uq_chat_runs_conversation_idempotency"),
    )
    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    registration_id = Column(String(32), ForeignKey("environment_registrations.id"), nullable=False)
    conversation_id = Column(String(32), ForeignKey("chat_conversations.id"), nullable=True)
    turn_id = Column(String(32), ForeignKey("chat_turns.id"), nullable=True, unique=True)
    idempotency_key = Column(String(128), nullable=True)
    session_id = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    output = Column(Text, nullable=True)
    trace_id = Column(String(64), nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)


class ChatConversation(Base):
    """A private, durable chat thread owned by one API key."""

    __tablename__ = "chat_conversations"
    __table_args__ = (
        Index("ix_chat_conversations_owner_updated", "project_id", "owner_api_key_id", "updated_at"),
        Index("ix_chat_conversations_project_deleted", "project_id", "deleted_at"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    owner_api_key_id = Column(String(32), ForeignKey("api_keys.id"), nullable=False)
    registration_id = Column(String(32), ForeignKey("environment_registrations.id"), nullable=False)
    session_id = Column(String(64), nullable=False)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class ChatTurn(Base):
    """One user prompt and its eventual assistant response in a conversation."""

    __tablename__ = "chat_turns"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence", name="uq_chat_turns_conversation_sequence"),
        UniqueConstraint("conversation_id", "idempotency_key", name="uq_chat_turns_conversation_idempotency"),
        Index("ix_chat_turns_conversation_created", "conversation_id", "created_at"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    conversation_id = Column(String(32), ForeignKey("chat_conversations.id"), nullable=False)
    sequence = Column(Integer, nullable=False)
    idempotency_key = Column(String(128), nullable=True)
    message = Column(Text, nullable=False)
    output = Column(Text, nullable=True)
    trace_id = Column(String(64), nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)


class ChannelSession(Base):
    __tablename__ = "channel_sessions"
    __table_args__ = (UniqueConstraint("project_id", "channel", "scoped_key", name="uq_channel_session_scope"),)
    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    channel = Column(String(64), nullable=False)
    scoped_key = Column(String(255), nullable=False)
    session_id = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class ChannelDelivery(Base):
    __tablename__ = "channel_deliveries"
    __table_args__ = (UniqueConstraint("project_id", "idempotency_key", name="uq_channel_delivery_idempotency"),)
    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    channel = Column(String(64), nullable=False)
    idempotency_key = Column(String(255), nullable=False)
    session_id = Column(String(64), nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    provider_message_id = Column(String(255), nullable=True)
    error = Column(Text, nullable=True)
    chat_run_id = Column(String(32), ForeignKey("chat_runs.id"), nullable=True)
    trace_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class ChannelConnection(Base):
    """Declarative provider configuration; values are represented only by secret IDs."""

    __tablename__ = "channel_connections"
    __table_args__ = (
        UniqueConstraint("project_id", "channel", "name", name="uq_channel_connection_name"),
        Index("ix_channel_connections_project_registration", "project_id", "registration_id"),
    )
    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    channel = Column(String(32), nullable=False)
    name = Column(String(128), nullable=False)
    registration_id = Column(String(32), ForeignKey("environment_registrations.id"), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    secret_refs = Column(JSON, default=dict, nullable=False)
    allowlist = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class ProviderSecret(Base):
    """A project-scoped encrypted provider credential envelope."""

    __tablename__ = "provider_secrets"
    __table_args__ = (
        UniqueConstraint("project_id", "provider", "name", name="uq_provider_secret_name"),
        Index("ix_provider_secrets_project_provider", "project_id", "provider"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    provider = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    encrypted_data_key = Column(Text, nullable=False)
    ciphertext = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    rotation_interval_days = Column(Integer, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_rotated_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class ProviderSecretAudit(Base):
    """Append-only metadata-only audit events for provider secret lifecycle actions."""

    __tablename__ = "provider_secret_audits"
    __table_args__ = (Index("ix_provider_secret_audits_project_created", "project_id", "created_at"),)

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    provider_secret_id = Column(String(32), nullable=False)
    action = Column(String(16), nullable=False)
    actor_api_key_id = Column(String(32), ForeignKey("api_keys.id"), nullable=True)
    details = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (Index("ix_api_keys_project_id", "project_id"),)

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    public_key = Column(String(64), unique=True, nullable=False, index=True)
    hashed_secret_key = Column(String(128), nullable=False)
    display_secret_key = Column(String(32), nullable=False)
    note = Column(String(255), default="")
    status = Column(String(20), default="active", nullable=False)
    role = Column(String(20), default="editor", nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class IngestionJob(Base):
    """A durable ingestion request awaiting local background processing."""

    __tablename__ = "ingestion_jobs"
    __table_args__ = (Index("ix_ingestion_jobs_status_created", "status", "created_at"),)

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String(16), default="pending", nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class AlertDestination(Base):
    """A project-scoped alert notification destination (Slack, Discord, SMTP)."""

    __tablename__ = "alert_destinations"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_alert_destinations_project_name"),
        Index("ix_alert_destinations_project_enabled", "project_id", "enabled"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    name = Column(String(128), nullable=False)
    destination_type = Column(String(32), nullable=False)
    config = Column(JSON, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    last_notified_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class Alert(Base):
    """A project-scoped operational or framework safety alert."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_project_created", "project_id", "created_at"),
        Index("ix_alerts_project_source", "project_id", "source"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    ingestion_job_id = Column(String(32), ForeignKey("ingestion_jobs.id"), nullable=True)
    trace_id = Column(String(64), nullable=True)
    source = Column(String(32), nullable=False)
    event_type = Column(String(64), nullable=False)
    severity = Column(String(16), nullable=False, default="warning")
    message = Column(String(500), nullable=False)
    metadata_field = Column("metadata", JSON, nullable=True)
    status = Column(String(16), nullable=False, default="open")
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class AlertRule(Base):
    """A project-scoped, operator-managed alert classification rule."""

    __tablename__ = "alert_rules"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_alert_rules_project_name"),
        Index("ix_alert_rules_project_enabled", "project_id", "enabled"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    name = Column(String(128), nullable=False)
    source = Column(String(32), nullable=True)
    event_type = Column(String(64), nullable=True)
    severity = Column(String(16), nullable=False, default="warning")
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class Trace(Base):
    """A root execution of an agent/workflow."""

    __tablename__ = "traces"
    __table_args__ = (
        Index("ix_traces_project_created", "project_id", "created_at"),
        Index("ix_traces_name", "project_id", "name"),
    )

    id = Column(String(64), primary_key=True)  # sent by the SDK (run_id)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False, default="")
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    session_id = Column(String(64), nullable=True)
    user_id = Column(String(128), nullable=True)
    version = Column(String(64), nullable=True)
    release = Column(String(64), nullable=True)
    environment = Column(String(64), nullable=True)
    environment_id = Column(String(32), nullable=True)
    registration_id = Column(String(32), nullable=True)
    definition_id = Column(String(32), nullable=True)
    definition_version = Column(String(64), nullable=True)
    attribution_status = Column(String(20), default="unattributed", nullable=False)
    input = Column(JSON, nullable=True)
    output = Column(JSON, nullable=True)
    metadata_field = Column("metadata", JSON, nullable=True)
    tags = Column(JSON, default=list, nullable=False)
    latency_ms = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    total_cost_currency = Column(String(3), nullable=True)
    total_cost_source = Column(String(64), nullable=True)
    error = Column(Text, nullable=True)


class Observation(Base):
    """Span inside a trace: generation (LLM), tool, step, retriever, etc."""

    __tablename__ = "observations"
    __table_args__ = (
        Index("ix_observations_trace", "trace_id", "start_time"),
        Index("ix_observations_parent", "parent_observation_id"),
        Index("ix_observations_type", "project_id", "type"),
    )

    id = Column(String(64), primary_key=True)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    trace_id = Column(String(64), ForeignKey("traces.id"), nullable=False)
    parent_observation_id = Column(String(64), nullable=True)
    type = Column(String(32), nullable=False, default="SPAN")  # TRACE/GENERATION/TOOL/SPAN/RETRIEVER...
    name = Column(String(255), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    level = Column(String(16), default="DEFAULT", nullable=False)
    status_message = Column(Text, nullable=True)
    model = Column(String(255), nullable=True)
    model_parameters = Column(JSON, nullable=True)
    input = Column(JSON, nullable=True)
    output = Column(JSON, nullable=True)
    usage = Column(JSON, nullable=True)
    cost = Column(Float, nullable=True)
    cost_currency = Column(String(3), nullable=True)
    cost_source = Column(String(64), nullable=True)
    metadata_field = Column("metadata", JSON, nullable=True)
    environment = Column(String(64), nullable=True)
    fingerprint = Column(JSON, nullable=True)


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (Index("ix_scores_trace", "trace_id"),)

    id = Column(String(64), primary_key=True)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    trace_id = Column(String(64), ForeignKey("traces.id"), nullable=False)
    observation_id = Column(String(64), nullable=True)
    name = Column(String(128), nullable=False)
    data_type = Column(String(16), default="NUMERIC", nullable=False)
    value = Column(Float, nullable=True)
    string_value = Column(String(500), nullable=True)
    comment = Column(Text, nullable=True)
    source = Column(String(32), default="API", nullable=False)  # API/EVAL/ANNOTATION
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class ScoreConfig(Base):
    __tablename__ = "score_configs"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_score_config_name"),)

    id = Column(String(64), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    name = Column(String(128), nullable=False)
    data_type = Column(String(16), default="NUMERIC", nullable=False)
    description = Column(Text, nullable=True)
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class EvalDataset(Base):
    __tablename__ = "eval_datasets"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_eval_dataset_name"),)

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class EvalDatasetItem(Base):
    __tablename__ = "eval_dataset_items"
    __table_args__ = (Index("ix_eval_dataset_items_dataset", "dataset_id"),)

    id = Column(String(32), primary_key=True, default=_uuid)
    dataset_id = Column(String(32), ForeignKey("eval_datasets.id"), nullable=False)
    trace_id = Column(String(64), ForeignKey("traces.id"), nullable=False)
    expected_output = Column(JSON, nullable=True)
    metadata_field = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class EvalRun(Base):
    __tablename__ = "eval_runs"
    __table_args__ = (Index("ix_eval_runs_project_created", "project_id", "created_at"),)

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    dataset_id = Column(String(32), ForeignKey("eval_datasets.id"), nullable=False)
    score_name = Column(String(128), nullable=False)
    status = Column(String(20), default="completed", nullable=False)
    total_cases = Column(Integer, default=0, nullable=False)
    passed_cases = Column(Integer, default=0, nullable=False)
    average_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class EvalRunResult(Base):
    __tablename__ = "eval_run_results"
    __table_args__ = (Index("ix_eval_run_results_run", "eval_run_id"),)

    id = Column(String(32), primary_key=True, default=_uuid)
    eval_run_id = Column(String(32), ForeignKey("eval_runs.id"), nullable=False)
    dataset_item_id = Column(String(32), ForeignKey("eval_dataset_items.id"), nullable=False)
    trace_id = Column(String(64), ForeignKey("traces.id"), nullable=False)
    actual_output = Column(JSON, nullable=True)
    value = Column(Float, nullable=False)
    score_id = Column(String(64), ForeignKey("scores.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class Prompt(Base):
    __tablename__ = "prompts"
    __table_args__ = (UniqueConstraint("project_id", "name", "version", name="uq_prompt_name_version"),)

    id = Column(String(64), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    name = Column(String(128), nullable=False)
    version = Column(Integer, nullable=False)
    type = Column(String(16), default="text", nullable=False)
    config = Column(JSON, nullable=True)
    content = Column(Text, nullable=True)
    labels = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class Approval(Base):
    """A human-in-the-loop approval gate tied to a run's tool call.

    Complete, central audit trail for HITL: who/what/when of every resolution.
    """

    __tablename__ = "approvals"
    __table_args__ = (
        UniqueConstraint("project_id", "approval_id", name="uq_approvals_project_approval_id"),
        Index("ix_approvals_trace", "trace_id"),
        Index("ix_approvals_status", "project_id", "status"),
        Index("ix_approvals_created", "project_id", "created_at"),
    )

    id = Column(String(64), primary_key=True)
    approval_id = Column(String(64), index=True, nullable=True)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    trace_id = Column(String(64), ForeignKey("traces.id"), nullable=True)
    tool_call_id = Column(String(64), nullable=True)
    tool_name = Column(String(128), nullable=False)
    requirement = Column(String(32), default="confirmation", nullable=False)  # confirmation|user_input|feedback|external_execution
    status = Column(String(24), default="pending", nullable=False)  # pending|approved|rejected|resolved|unauthorized
    tool_arguments = Column(JSON, nullable=True)
    confirmation = Column(Boolean, nullable=True)
    confirmation_note = Column(Text, nullable=True)
    user_input = Column(JSON, nullable=True)
    feedback = Column(JSON, nullable=True)
    resolved_by = Column(String(128), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    metadata_field = Column("metadata", JSON, nullable=True)


class PrivacyAuditLog(Base):
    """Append-only record of data subject requests without storing the subject ID."""

    __tablename__ = "privacy_audit_logs"
    __table_args__ = (Index("ix_privacy_audit_logs_project_created", "project_id", "created_at"),)

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    action = Column(String(16), nullable=False)
    subject_hash = Column(String(64), nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class PolicyDecisionAudit(Base):
    """Append-only audit trail for capability policy evaluations."""

    __tablename__ = "policy_decision_audits"
    __table_args__ = (
        Index("ix_policy_decision_audits_project_created", "project_id", "created_at"),
        Index("ix_policy_decision_audits_registration_created", "registration_id", "created_at"),
    )

    id = Column(String(32), primary_key=True, default=_uuid)
    project_id = Column(String(32), ForeignKey("projects.id"), nullable=False)
    registration_id = Column(String(32), ForeignKey("environment_registrations.id"), nullable=True)
    action = Column(String(32), nullable=False)
    decision = Column(String(24), nullable=False)
    reasons = Column(JSON, default=list, nullable=False)
    request = Column(JSON, nullable=False)
    policy = Column(JSON, nullable=False)
    approval_id = Column(String(64), nullable=True)
    actor_api_key_id = Column(String(32), ForeignKey("api_keys.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
