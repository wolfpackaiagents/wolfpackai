"""Regression coverage for the local AMP Phase 2 demo fixture."""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import demo_seed
from app.models.entities import (
    Alert,
    ApiKey,
    Approval,
    Environment,
    EnvironmentRegistration,
    EvalDataset,
    EvalDatasetItem,
    EvalRun,
    EvalRunResult,
    MeshDefinition,
    MeshInteraction,
    RegistrationHeartbeat,
    Observation,
    Organization,
    Project,
    ScoreConfig,
    Trace,
)
from app.core.database import Base


def test_phase_2_demo_seed_is_context_rich_and_idempotent(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr(demo_seed, "engine", engine)
    monkeypatch.setattr(demo_seed, "SessionLocal", Session)

    with Session() as db:
        organization = Organization(id="demo-seed-organization", name="Demo Seed Organization")
        db.add(organization)
        db.add(Project(id="demo-seed-project", organization_id=organization.id, name="Demo Seed Project"))
        db.commit()

    demo_seed.seed_demo()
    demo_seed.seed_demo()

    with Session() as db:
        project = db.query(Project).filter_by(id="demo-seed-project").one()
        environment = db.query(Environment).filter_by(project_id=project.id, slug="development").one()
        definition = db.query(MeshDefinition).filter_by(project_id=project.id, key="weather-operations", version="1.0.0").one()
        registration = db.query(EnvironmentRegistration).filter_by(environment_id=environment.id, definition_id=definition.id).one()
        traces = db.query(Trace).filter_by(project_id=project.id, registration_id=registration.id).all()
        alert_states = {alert.status for alert in db.query(Alert).filter_by(project_id=project.id, source="guardrail").all()}
        approval = db.query(Approval).filter_by(project_id=project.id, approval_id="demo_approval_1").one()
        dataset = db.query(EvalDataset).filter_by(project_id=project.id, name="weather-operations-regression").one()
        run = db.query(EvalRun).filter_by(project_id=project.id, dataset_id=dataset.id).one()

        assert definition.kind == "agent"
        assert registration.enabled is True
        assert db.query(RegistrationHeartbeat).filter_by(project_id=project.id).count() == 5
        assert len(traces) == 3
        assert all(trace.session_id and trace.metadata_field["agent"]["key"] == "weather-operations" for trace in traces)
        assert db.query(Observation).filter_by(project_id=project.id).count() == 6
        assert {"open", "acknowledged", "resolved"} <= alert_states
        assert approval.trace_id == "demo_weather_trace_alert"
        assert approval.metadata_field["session_id"] == "weather-ops-session-2026-08-23"
        assert approval.metadata_field["agent_key"] == "weather-operations"
        assert db.query(ScoreConfig).filter_by(project_id=project.id).count() == 2
        assert db.query(EvalDatasetItem).filter_by(dataset_id=dataset.id).count() == 2
        assert run.average_score == 0.5
        assert db.query(EvalRunResult).filter_by(eval_run_id=run.id).count() == 2
        interactions = db.query(MeshInteraction).filter_by(project_id=project.id).all()
        assert {(interaction.interaction_type, interaction.operation, interaction.tool_name) for interaction in interactions} == {
            ("route", "team.route", None),
            ("delegation", "team.delegate", None),
            ("tool", "tool.invoke", "search_support_knowledge"),
            ("handoff", "team.handoff", None),
        }
        assert len({interaction.trace_id for interaction in interactions}) == 1
        assert interactions[0].trace_id in {trace.id for trace in traces}

    demo_seed.seed_demo(reset=True)
    with Session() as db:
        e2e_keys = db.query(ApiKey).filter(ApiKey.public_key.like("pk-wp-e2e-%")).all()
        assert len(e2e_keys) == 8
        assert all(key.project_id == "demo-seed-project" and key.role == "admin" for key in e2e_keys)
