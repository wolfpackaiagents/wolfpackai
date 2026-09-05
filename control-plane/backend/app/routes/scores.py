"""Public score and score-configuration API for trace evaluation."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.auth import AuthContext, require_role, resolve_project_id
from ..models.entities import Score, ScoreConfig, Trace

router = APIRouter(prefix="/api/public")


class ScoreConfigBody(BaseModel):
    name: str
    data_type: str = "NUMERIC"
    description: Optional[str] = None
    config: Optional[dict] = None


class ScoreBody(BaseModel):
    trace_id: str
    name: str
    value: Optional[float] = None
    string_value: Optional[str] = None
    comment: Optional[str] = None
    source: str = "API"


@router.get("/score-configs")
def list_configs(auth: Tuple[str, Session] = Depends(resolve_project_id)):
    project_id, db = auth
    return [_config_dict(item) for item in db.query(ScoreConfig).filter_by(project_id=project_id).order_by(ScoreConfig.name).all()]


@router.post("/score-configs")
def create_config(body: ScoreConfigBody, auth: AuthContext = Depends(require_role("editor"))):
    project_id, db = auth
    if db.query(ScoreConfig).filter_by(project_id=project_id, name=body.name).first():
        raise HTTPException(status_code=409, detail="Score config already exists")
    config = ScoreConfig(project_id=project_id, **body.model_dump())
    db.add(config)
    db.commit()
    db.refresh(config)
    return _config_dict(config)


@router.get("/scores")
def list_scores(trace_id: Optional[str] = None, environment_id: Optional[str] = None, registration_id: Optional[str] = None, from_: Optional[datetime] = Query(default=None, alias="from"), to: Optional[datetime] = None, auth: Tuple[str, Session] = Depends(resolve_project_id)):
    project_id, db = auth
    query = db.query(Score).join(Trace, Trace.id == Score.trace_id).filter(Score.project_id == project_id)
    if trace_id:
        query = query.filter(Score.trace_id == trace_id)
    if environment_id: query = query.filter(Trace.environment_id == environment_id)
    if registration_id: query = query.filter(Trace.registration_id == registration_id)
    if from_: query = query.filter(Trace.timestamp >= from_)
    if to: query = query.filter(Trace.timestamp <= to)
    return [_score_dict(item) for item in query.order_by(Score.created_at.desc()).all()]


@router.get("/quality/overview")
def quality_overview(environment_id: Optional[str] = None, registration_id: Optional[str] = None, from_: Optional[datetime] = Query(default=None, alias="from"), to: Optional[datetime] = None, auth: AuthContext = Depends(require_role("read_only"))):
    query = auth.db.query(Score).join(Trace, Trace.id == Score.trace_id).filter(Score.project_id == auth.project_id)
    if environment_id: query = query.filter(Trace.environment_id == environment_id)
    if registration_id: query = query.filter(Trace.registration_id == registration_id)
    if from_: query = query.filter(Trace.timestamp >= from_)
    if to: query = query.filter(Trace.timestamp <= to)
    scores = query.order_by(Score.created_at).all()
    numeric = [score.value for score in scores if score.value is not None]
    by_name = defaultdict(list)
    for score in scores:
        if score.value is not None: by_name[score.name].append(score.value)
    return {"scored_count": len(scores), "numeric_count": len(numeric), "average": sum(numeric) / len(numeric) if numeric else None, "metrics": [{"name": name, "average": sum(values) / len(values), "count": len(values)} for name, values in by_name.items()], "trend": [{"timestamp": score.created_at.isoformat(), "name": score.name, "value": score.value} for score in scores if score.value is not None], "distribution": [{"name": name, "count": len(values)} for name, values in by_name.items()]}


@router.post("/scores")
def create_score(body: ScoreBody, auth: AuthContext = Depends(require_role("editor"))):
    project_id, db = auth
    if not db.query(Trace).filter_by(id=body.trace_id, project_id=project_id).first():
        raise HTTPException(status_code=404, detail="Trace not found")
    score = Score(id=uuid.uuid4().hex, project_id=project_id, data_type="CATEGORICAL" if body.string_value is not None else "NUMERIC", **body.model_dump())
    db.add(score)
    db.commit()
    db.refresh(score)
    return _score_dict(score)


def _config_dict(config: ScoreConfig) -> dict:
    return {"id": config.id, "name": config.name, "data_type": config.data_type, "description": config.description, "config": config.config}


def _score_dict(score: Score) -> dict:
    return {"id": score.id, "trace_id": score.trace_id, "name": score.name, "data_type": score.data_type, "value": score.value, "string_value": score.string_value, "comment": score.comment, "source": score.source, "created_at": score.created_at.isoformat()}
