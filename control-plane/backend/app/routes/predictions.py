"""Predictions API: multi-agent prediction runs, personas, interactions and accuracy.

Every prediction run groups multiple agent personas. Traces and scores are linked
so the dedicated AI Predictions UI can display them without polluting the main
operational observability views."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.auth import AuthContext, require_role, resolve_project_id
from ..models.entities import (
    PredictionAgentRun,
    PredictionEntity,
    PredictionEntityRevision,
    PredictionEvent,
    PredictionRelationship,
    PredictionRound,
    PredictionRun,
    Score,
    Trace,
)

router = APIRouter(prefix="/api/public")


class CreatePredictionBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    seed_summary: Optional[str] = None
    horizon_date: Optional[datetime] = None
    scenario_params: Optional[dict] = None
    personas: list[dict] = Field(default_factory=list)
    report: Optional[dict] = None


class AgentPredictionBody(BaseModel):
    persona_name: str
    entity_id: Optional[str] = None
    persona_profile: Optional[dict] = None
    trace_id: Optional[str] = None
    prediction: Optional[Any] = None
    confidence: Optional[float] = None
    interactions: Optional[list] = None


class PredictionEvalBody(BaseModel):
    accuracy_score: float = Field(..., ge=0, le=1)


class PredictionEntityBody(BaseModel):
    entity_type: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    state: dict = Field(default_factory=dict)
    metadata: Optional[dict] = None


class PredictionRelationshipBody(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relationship_type: str = Field(min_length=1, max_length=64)
    attributes: dict = Field(default_factory=dict)


class PredictionRoundBody(BaseModel):
    number: Optional[int] = Field(default=None, ge=1)
    data: dict = Field(default_factory=dict)


class PredictionEventBody(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    payload: dict = Field(default_factory=dict)
    round_id: Optional[str] = None
    entity_id: Optional[str] = None
    agent_run_id: Optional[str] = None
    idempotency_key: Optional[str] = Field(default=None, min_length=1, max_length=128)


class PredictionEntityRevisionBody(BaseModel):
    state: dict = Field(default_factory=dict)


@router.get("/predictions")
def list_predictions(
    status: Optional[str] = None,
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = None,
    page: int = Query(default=0, ge=0, le=10_000),
    per_page: int = Query(default=20, ge=1, le=100),
    auth: AuthContext = Depends(require_role("read_only")),
):
    q = auth.db.query(PredictionRun).filter(PredictionRun.project_id == auth.project_id)
    if status:
        q = q.filter(PredictionRun.status == status)
    from_date = _optional_datetime(from_)
    to_date = _optional_datetime(to)
    if from_date:
        q = q.filter(PredictionRun.created_at >= from_date)
    if to_date:
        q = q.filter(PredictionRun.created_at <= to_date)
    total = q.count()
    rows = q.order_by(PredictionRun.created_at.desc()).offset(page * per_page).limit(per_page).all()
    counts = {
        run_id: count
        for run_id, count in auth.db.query(
            PredictionAgentRun.prediction_run_id, func.count(PredictionAgentRun.id)
        ).filter(PredictionAgentRun.prediction_run_id.in_([r.id for r in rows] or [""])).group_by(
            PredictionAgentRun.prediction_run_id
        ).all()
    }
    return {
        "predictions": [_run_short_dict(r, counts.get(r.id, 0)) for r in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
    }


@router.post("/predictions", status_code=201)
def create_prediction(body: CreatePredictionBody, auth: AuthContext = Depends(require_role("editor"))):
    run = PredictionRun(
        project_id=auth.project_id,
        name=body.name,
        seed_summary=body.seed_summary,
        horizon_date=body.horizon_date,
        scenario_params=body.scenario_params or {},
        personas=body.personas,
        report=body.report,
        status="running",
    )
    auth.db.add(run)
    auth.db.commit()
    auth.db.refresh(run)
    return _run_full_dict(run, auth.db)


@router.get("/predictions/{prediction_id}")
def get_prediction(
    prediction_id: str,
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = None,
    environment_id: Optional[str] = None,
    registration_id: Optional[str] = None,
    auth: AuthContext = Depends(require_role("read_only")),
):
    run = auth.db.query(PredictionRun).filter_by(id=prediction_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return _run_full_dict(run, auth.db)


@router.patch("/predictions/{prediction_id}")
def update_prediction(prediction_id: str, body: CreatePredictionBody, auth: AuthContext = Depends(require_role("editor"))):
    run = auth.db.query(PredictionRun).filter_by(id=prediction_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Prediction not found")
    for attr in ("name", "seed_summary", "horizon_date", "scenario_params", "personas"):
        val = getattr(body, attr, None)
        if val is not None:
            setattr(run, attr, val)
    if body.scenario_params is not None:
        run.scenario_params = body.scenario_params
    auth.db.commit()
    auth.db.refresh(run)
    return _run_full_dict(run, auth.db)


@router.delete("/predictions/{prediction_id}", status_code=204)
def delete_prediction(prediction_id: str, auth: AuthContext = Depends(require_role("admin"))):
    run = auth.db.query(PredictionRun).filter_by(id=prediction_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Prediction not found")
    auth.db.query(PredictionEvent).filter_by(prediction_run_id=prediction_id).delete()
    auth.db.query(PredictionEntityRevision).filter_by(prediction_run_id=prediction_id).delete()
    auth.db.query(PredictionRelationship).filter_by(prediction_run_id=prediction_id).delete()
    auth.db.query(PredictionRound).filter_by(prediction_run_id=prediction_id).delete()
    auth.db.query(PredictionAgentRun).filter_by(prediction_run_id=prediction_id).delete()
    auth.db.query(PredictionEntity).filter_by(prediction_run_id=prediction_id).delete()
    auth.db.delete(run)
    auth.db.commit()


@router.post("/predictions/{prediction_id}/complete", status_code=200)
def complete_prediction(prediction_id: str, auth: AuthContext = Depends(require_role("editor"))):
    run = auth.db.query(PredictionRun).filter_by(id=prediction_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Prediction not found")
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    auth.db.commit()
    auth.db.refresh(run)
    return _run_full_dict(run, auth.db)


@router.get("/predictions/{prediction_id}/agents")
def list_prediction_agents(
    prediction_id: str,
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = None,
    environment_id: Optional[str] = None,
    registration_id: Optional[str] = None,
    auth: AuthContext = Depends(require_role("read_only")),
):
    run = auth.db.query(PredictionRun).filter_by(id=prediction_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Prediction not found")
    agents = auth.db.query(PredictionAgentRun).filter_by(prediction_run_id=prediction_id).order_by(PredictionAgentRun.created_at).all()
    return {"prediction_id": prediction_id, "agents": [_agent_dict(a) for a in agents]}


@router.post("/predictions/{prediction_id}/agents", status_code=201)
def add_prediction_agent(prediction_id: str, body: AgentPredictionBody, auth: AuthContext = Depends(require_role("editor"))):
    run = auth.db.query(PredictionRun).filter_by(id=prediction_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Prediction not found")
    if body.entity_id:
        _run_entity(auth.db, run, auth.project_id, body.entity_id)
    agent = PredictionAgentRun(
        prediction_run_id=prediction_id,
        project_id=auth.project_id,
        entity_id=body.entity_id,
        persona_name=body.persona_name,
        persona_profile=body.persona_profile or {},
        trace_id=body.trace_id,
        prediction=body.prediction,
        confidence=body.confidence,
        interactions=body.interactions or [],
        status="completed" if body.prediction else "running",
    )
    auth.db.add(agent)
    auth.db.commit()
    auth.db.refresh(agent)
    return _agent_dict(agent)


@router.get("/predictions/{prediction_id}/simulation")
def get_prediction_simulation(prediction_id: str, auth: AuthContext = Depends(require_role("read_only"))):
    run = _prediction_run(auth, prediction_id)
    entities = auth.db.query(PredictionEntity).filter_by(prediction_run_id=run.id, project_id=auth.project_id).order_by(PredictionEntity.created_at).all()
    relationships = auth.db.query(PredictionRelationship).filter_by(prediction_run_id=run.id, project_id=auth.project_id).order_by(PredictionRelationship.created_at).all()
    rounds = auth.db.query(PredictionRound).filter_by(prediction_run_id=run.id, project_id=auth.project_id).order_by(PredictionRound.number).all()
    events = auth.db.query(PredictionEvent).filter_by(prediction_run_id=run.id, project_id=auth.project_id).order_by(PredictionEvent.sequence).all()
    revisions = auth.db.query(PredictionEntityRevision).filter_by(prediction_run_id=run.id, project_id=auth.project_id).order_by(
        PredictionEntityRevision.entity_id, PredictionEntityRevision.revision
    ).all()
    return {
        "prediction_id": run.id,
        "entities": [_entity_dict(row) for row in entities],
        "relationships": [_relationship_dict(row) for row in relationships],
        "rounds": [_round_dict(row) for row in rounds],
        "events": [_event_dict(row) for row in events],
        "revisions": [_revision_dict(row) for row in revisions],
    }


@router.post("/predictions/{prediction_id}/entities", status_code=201)
def create_prediction_entity(prediction_id: str, body: PredictionEntityBody, auth: AuthContext = Depends(require_role("editor"))):
    run = _mutable_prediction_run(auth, prediction_id)
    entity = PredictionEntity(
        prediction_run_id=run.id,
        project_id=auth.project_id,
        entity_type=body.entity_type,
        name=body.name,
        state=body.state,
        metadata_field=body.metadata,
    )
    auth.db.add(entity)
    auth.db.commit()
    auth.db.refresh(entity)
    return _entity_dict(entity)


@router.post("/predictions/{prediction_id}/relationships", status_code=201)
def create_prediction_relationship(prediction_id: str, body: PredictionRelationshipBody, auth: AuthContext = Depends(require_role("editor"))):
    run = _mutable_prediction_run(auth, prediction_id)
    _run_entity(auth.db, run, auth.project_id, body.source_entity_id)
    _run_entity(auth.db, run, auth.project_id, body.target_entity_id)
    relationship = PredictionRelationship(
        prediction_run_id=run.id,
        project_id=auth.project_id,
        source_entity_id=body.source_entity_id,
        target_entity_id=body.target_entity_id,
        relationship_type=body.relationship_type,
        attributes=body.attributes,
    )
    auth.db.add(relationship)
    auth.db.commit()
    auth.db.refresh(relationship)
    return _relationship_dict(relationship)


@router.get("/predictions/{prediction_id}/rounds")
def list_prediction_rounds(prediction_id: str, auth: AuthContext = Depends(require_role("read_only"))):
    run = _prediction_run(auth, prediction_id)
    rows = auth.db.query(PredictionRound).filter_by(prediction_run_id=run.id, project_id=auth.project_id).order_by(PredictionRound.number).all()
    return {"prediction_id": run.id, "rounds": [_round_dict(row) for row in rows]}


@router.post("/predictions/{prediction_id}/rounds", status_code=201)
def create_prediction_round(prediction_id: str, body: PredictionRoundBody, auth: AuthContext = Depends(require_role("editor"))):
    run = _mutable_prediction_run(auth, prediction_id, lock=True)
    number = body.number
    if number is None:
        number = (auth.db.query(func.max(PredictionRound.number)).filter_by(prediction_run_id=run.id).scalar() or 0) + 1
    existing = auth.db.query(PredictionRound).filter_by(prediction_run_id=run.id, number=number).first()
    if existing:
        raise HTTPException(status_code=409, detail="Round number already exists")
    round_ = PredictionRound(prediction_run_id=run.id, project_id=auth.project_id, number=number, data=body.data)
    auth.db.add(round_)
    auth.db.commit()
    auth.db.refresh(round_)
    return _round_dict(round_)


@router.post("/predictions/{prediction_id}/rounds/{round_id}/close")
def close_prediction_round(prediction_id: str, round_id: str, auth: AuthContext = Depends(require_role("editor"))):
    run = _mutable_prediction_run(auth, prediction_id)
    round_ = _run_round(auth.db, run, auth.project_id, round_id)
    if round_.status == "closed":
        return _round_dict(round_)
    round_.status = "closed"
    round_.closed_at = datetime.now(timezone.utc)
    auth.db.commit()
    auth.db.refresh(round_)
    return _round_dict(round_)


@router.get("/predictions/{prediction_id}/events")
def list_prediction_events(prediction_id: str, after_sequence: int = Query(default=0, ge=0), auth: AuthContext = Depends(require_role("read_only"))):
    run = _prediction_run(auth, prediction_id)
    rows = auth.db.query(PredictionEvent).filter(
        PredictionEvent.prediction_run_id == run.id,
        PredictionEvent.project_id == auth.project_id,
        PredictionEvent.sequence > after_sequence,
    ).order_by(PredictionEvent.sequence).all()
    return {"prediction_id": run.id, "events": [_event_dict(row) for row in rows]}


@router.post("/predictions/{prediction_id}/events", status_code=201)
def create_prediction_event(prediction_id: str, body: PredictionEventBody, auth: AuthContext = Depends(require_role("editor"))):
    # Locking the run serializes sequence allocation on databases that support row locks.
    run = _mutable_prediction_run(auth, prediction_id, lock=True)
    if body.idempotency_key:
        existing = auth.db.query(PredictionEvent).filter_by(prediction_run_id=run.id, idempotency_key=body.idempotency_key).first()
        if existing:
            return _event_dict(existing)
    if body.round_id:
        _run_round(auth.db, run, auth.project_id, body.round_id)
    if body.entity_id:
        _run_entity(auth.db, run, auth.project_id, body.entity_id)
    if body.agent_run_id and not auth.db.query(PredictionAgentRun).filter_by(id=body.agent_run_id, prediction_run_id=run.id, project_id=auth.project_id).first():
        raise HTTPException(status_code=404, detail="Agent run not found")
    sequence = (auth.db.query(func.max(PredictionEvent.sequence)).filter_by(prediction_run_id=run.id).scalar() or 0) + 1
    event = PredictionEvent(
        prediction_run_id=run.id,
        project_id=auth.project_id,
        round_id=body.round_id,
        entity_id=body.entity_id,
        agent_run_id=body.agent_run_id,
        sequence=sequence,
        event_type=body.event_type,
        payload=body.payload,
        idempotency_key=body.idempotency_key,
    )
    auth.db.add(event)
    auth.db.commit()
    auth.db.refresh(event)
    return _event_dict(event)


@router.get("/predictions/{prediction_id}/entities/{entity_id}/revisions")
def list_prediction_entity_revisions(prediction_id: str, entity_id: str, auth: AuthContext = Depends(require_role("read_only"))):
    run = _prediction_run(auth, prediction_id)
    _run_entity(auth.db, run, auth.project_id, entity_id)
    rows = auth.db.query(PredictionEntityRevision).filter_by(prediction_run_id=run.id, project_id=auth.project_id, entity_id=entity_id).order_by(PredictionEntityRevision.revision).all()
    return {"prediction_id": run.id, "entity_id": entity_id, "revisions": [_revision_dict(row) for row in rows]}


@router.post("/predictions/{prediction_id}/entities/{entity_id}/revisions", status_code=201)
def create_prediction_entity_revision(prediction_id: str, entity_id: str, body: PredictionEntityRevisionBody, auth: AuthContext = Depends(require_role("editor"))):
    run = _mutable_prediction_run(auth, prediction_id, lock=True)
    _run_entity(auth.db, run, auth.project_id, entity_id)
    revision = (auth.db.query(func.max(PredictionEntityRevision.revision)).filter_by(entity_id=entity_id).scalar() or 0) + 1
    row = PredictionEntityRevision(prediction_run_id=run.id, project_id=auth.project_id, entity_id=entity_id, revision=revision, state=body.state)
    auth.db.add(row)
    auth.db.commit()
    auth.db.refresh(row)
    return _revision_dict(row)


@router.patch("/predictions/{prediction_id}/agents/{agent_id}")
def update_prediction_agent(prediction_id: str, agent_id: str, body: AgentPredictionBody, auth: AuthContext = Depends(require_role("editor"))):
    agent = auth.db.query(PredictionAgentRun).filter_by(
        id=agent_id, prediction_run_id=prediction_id, project_id=auth.project_id
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent run not found")
    for attr in ("trace_id", "prediction", "confidence", "interactions", "persona_profile"):
        val = getattr(body, attr, None)
        if val is not None:
            setattr(agent, attr, val)
    if body.prediction is not None:
        agent.status = "completed"
    auth.db.commit()
    auth.db.refresh(agent)
    return _agent_dict(agent)


@router.get("/predictions/{prediction_id}/interactions")
def get_prediction_interactions(
    prediction_id: str,
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = None,
    environment_id: Optional[str] = None,
    registration_id: Optional[str] = None,
    auth: AuthContext = Depends(require_role("read_only")),
):
    run = auth.db.query(PredictionRun).filter_by(id=prediction_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Prediction not found")
    agents = auth.db.query(PredictionAgentRun).filter_by(prediction_run_id=prediction_id).all()
    nodes: list[dict] = []
    edges: list[dict] = []
    for agent in agents:
        node_id = f"agent_{agent.id}"
        nodes.append({"id": node_id, "label": agent.persona_name, "confidence": agent.confidence, "status": agent.status})
        for interaction in (agent.interactions or []):
            target_label = interaction.get("target", "")
            target = next((a for a in agents if a.persona_name == target_label), None)
            if target:
                edges.append({
                    "source": node_id,
                    "target": f"agent_{target.id}",
                    "type": interaction.get("type", "message"),
                    "content": interaction.get("content", ""),
                    "round": interaction.get("round", 0),
                })
    return {"prediction_id": prediction_id, "nodes": nodes, "edges": edges}


@router.post("/predictions/{prediction_id}/eval", status_code=200)
def evaluate_prediction(prediction_id: str, body: PredictionEvalBody, auth: AuthContext = Depends(require_role("editor"))):
    run = auth.db.query(PredictionRun).filter_by(id=prediction_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Prediction not found")
    run.accuracy_score = body.accuracy_score
    run.status = "evaluated"
    auth.db.commit()
    auth.db.refresh(run)
    return {"id": run.id, "accuracy_score": run.accuracy_score, "status": run.status}


@router.get("/predictions/{prediction_id}/traces")
def get_prediction_traces(
    prediction_id: str,
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = None,
    environment_id: Optional[str] = None,
    registration_id: Optional[str] = None,
    auth: AuthContext = Depends(require_role("read_only")),
):
    run = auth.db.query(PredictionRun).filter_by(id=prediction_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Prediction not found")
    agents = auth.db.query(PredictionAgentRun).filter_by(prediction_run_id=prediction_id).all()
    trace_ids = [a.trace_id for a in agents if a.trace_id]
    traces = auth.db.query(Trace).filter(Trace.project_id == auth.project_id, Trace.id.in_(trace_ids)).all() if trace_ids else []
    return {"prediction_id": prediction_id, "traces": [_trace_dict(t) for t in traces]}


@router.get("/predictions/{prediction_id}/scores")
def get_prediction_scores(
    prediction_id: str,
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = None,
    environment_id: Optional[str] = None,
    registration_id: Optional[str] = None,
    auth: AuthContext = Depends(require_role("read_only")),
):
    run = auth.db.query(PredictionRun).filter_by(id=prediction_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Prediction not found")
    agents = auth.db.query(PredictionAgentRun).filter_by(prediction_run_id=prediction_id).all()
    trace_ids = [a.trace_id for a in agents if a.trace_id]
    scores = auth.db.query(Score).filter(Score.project_id == auth.project_id, Score.trace_id.in_(trace_ids)).all() if trace_ids else []
    return {"prediction_id": prediction_id, "scores": [_score_dict(s) for s in scores]}


@router.get("/predictions/{prediction_id}/summary")
def prediction_summary(
    prediction_id: str,
    from_: Optional[datetime] = Query(default=None, alias="from"),
    to: Optional[datetime] = None,
    environment_id: Optional[str] = None,
    registration_id: Optional[str] = None,
    auth: AuthContext = Depends(require_role("read_only")),
):
    run = auth.db.query(PredictionRun).filter_by(id=prediction_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Prediction not found")
    agents = auth.db.query(PredictionAgentRun).filter_by(prediction_run_id=prediction_id).all()
    agent_names = [a.persona_name for a in agents]
    convergences = _compute_convergences(agents)
    return {
        "name": run.name,
        "status": run.status,
        "accuracy_score": run.accuracy_score,
        "agent_count": len(agents),
        "agents": agent_names,
        "convergences": convergences,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def _prediction_run(auth: AuthContext, prediction_id: str) -> PredictionRun:
    run = auth.db.query(PredictionRun).filter_by(id=prediction_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return run


def _mutable_prediction_run(auth: AuthContext, prediction_id: str, lock: bool = False) -> PredictionRun:
    query = auth.db.query(PredictionRun).filter_by(id=prediction_id, project_id=auth.project_id)
    if lock:
        query = query.with_for_update()
    run = query.first()
    if not run:
        raise HTTPException(status_code=404, detail="Prediction not found")
    if run.status in ("completed", "evaluated"):
        raise HTTPException(status_code=409, detail="Prediction is in a terminal state")
    return run


def _run_entity(db: Session, run: PredictionRun, project_id: str, entity_id: str) -> PredictionEntity:
    entity = db.query(PredictionEntity).filter_by(id=entity_id, prediction_run_id=run.id, project_id=project_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Simulation entity not found")
    return entity


def _run_round(db: Session, run: PredictionRun, project_id: str, round_id: str) -> PredictionRound:
    round_ = db.query(PredictionRound).filter_by(id=round_id, prediction_run_id=run.id, project_id=project_id).first()
    if not round_:
        raise HTTPException(status_code=404, detail="Simulation round not found")
    return round_


def _entity_dict(entity: PredictionEntity) -> dict:
    return {
        "id": entity.id,
        "prediction_run_id": entity.prediction_run_id,
        "entity_type": entity.entity_type,
        "name": entity.name,
        "state": entity.state,
        "metadata": entity.metadata_field,
        "created_at": entity.created_at.isoformat(),
    }


def _relationship_dict(relationship: PredictionRelationship) -> dict:
    return {
        "id": relationship.id,
        "prediction_run_id": relationship.prediction_run_id,
        "source_entity_id": relationship.source_entity_id,
        "target_entity_id": relationship.target_entity_id,
        "relationship_type": relationship.relationship_type,
        "attributes": relationship.attributes,
        "created_at": relationship.created_at.isoformat(),
    }


def _round_dict(round_: PredictionRound) -> dict:
    return {
        "id": round_.id,
        "prediction_run_id": round_.prediction_run_id,
        "number": round_.number,
        "status": round_.status,
        "data": round_.data,
        "created_at": round_.created_at.isoformat(),
        "closed_at": round_.closed_at.isoformat() if round_.closed_at else None,
    }


def _event_dict(event: PredictionEvent) -> dict:
    return {
        "id": event.id,
        "prediction_run_id": event.prediction_run_id,
        "round_id": event.round_id,
        "entity_id": event.entity_id,
        "agent_run_id": event.agent_run_id,
        "sequence": event.sequence,
        "event_type": event.event_type,
        "payload": event.payload,
        "idempotency_key": event.idempotency_key,
        "created_at": event.created_at.isoformat(),
    }


def _revision_dict(revision: PredictionEntityRevision) -> dict:
    return {
        "id": revision.id,
        "prediction_run_id": revision.prediction_run_id,
        "entity_id": revision.entity_id,
        "revision": revision.revision,
        "state": revision.state,
        "created_at": revision.created_at.isoformat(),
    }


def _compute_convergences(agents: list[PredictionAgentRun]) -> list[dict]:
    predictions = [(a.persona_name, a.prediction, a.confidence) for a in agents if a.prediction]
    if len(predictions) < 2:
        return []
    convergences = []
    for i, (name_i, pred_i, conf_i) in enumerate(predictions):
        for j, (name_j, pred_j, conf_j) in enumerate(predictions):
            if i >= j:
                continue
            if isinstance(pred_i, dict) and isinstance(pred_j, dict):
                common = set(pred_i.keys()) & set(pred_j.keys())
                if common:
                    match_count = sum(1 for k in common if pred_i.get(k) == pred_j.get(k))
                    rate = match_count / len(common) if common else 0
                    convergences.append({"agents": [name_i, name_j], "rate": rate, "confidence_avg": ((conf_i or 0) + (conf_j or 0)) / 2})
    return sorted(convergences, key=lambda c: c["rate"], reverse=True)


def _optional_datetime(value: Optional[str]) -> Optional[datetime]:
    """Treat empty scope values as absent while retaining FastAPI's date validation."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid datetime query parameter") from exc


def _run_short_dict(run: PredictionRun, agent_count: int = 0) -> dict:
    return {
        "id": run.id,
        "agent_count": agent_count,
        "name": run.name,
        "seed_summary": run.seed_summary,
        "horizon_date": run.horizon_date.isoformat() if run.horizon_date else None,
        "status": run.status,
        "accuracy_score": run.accuracy_score,
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def _run_full_dict(run: PredictionRun, db: Session) -> dict:
    agents = db.query(PredictionAgentRun).filter_by(prediction_run_id=run.id).order_by(PredictionAgentRun.created_at).all() if run.id else []
    return {
        "id": run.id,
        "name": run.name,
        "seed_summary": run.seed_summary,
        "horizon_date": run.horizon_date.isoformat() if run.horizon_date else None,
        "scenario_params": run.scenario_params,
        "personas": run.personas,
        "status": run.status,
        "report": run.report,
        "accuracy_score": run.accuracy_score,
        "agent_count": len(agents),
        "agents": [_agent_dict(a) for a in agents],
        "created_at": run.created_at.isoformat(),
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def _agent_dict(agent: PredictionAgentRun) -> dict:
    return {
        "id": agent.id,
        "entity_id": agent.entity_id,
        "persona_name": agent.persona_name,
        "persona_profile": agent.persona_profile,
        "trace_id": agent.trace_id,
        "prediction": agent.prediction,
        "confidence": agent.confidence,
        "interactions": agent.interactions,
        "status": agent.status,
        "created_at": agent.created_at.isoformat(),
    }


def _trace_dict(t: Trace) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "session_id": t.session_id,
        "input": t.input,
        "output": t.output,
        "latency_ms": t.latency_ms,
        "total_cost": t.total_cost,
        "created_at": t.created_at.isoformat(),
    }


def _score_dict(s: Score) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "value": s.value,
        "source": s.source,
        "comment": s.comment,
        "created_at": s.created_at.isoformat(),
    }
