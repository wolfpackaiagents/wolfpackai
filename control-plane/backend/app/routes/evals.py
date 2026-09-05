"""Trace-backed deterministic evaluation datasets and runs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.auth import AuthContext, require_role
from ..models.entities import EvalDataset, EvalDatasetItem, EvalRun, EvalRunResult, Score, Trace

router = APIRouter(prefix="/api/public")


class EvalDatasetItemBody(BaseModel):
    trace_id: str
    expected_output: Any = None
    metadata: Optional[dict] = None


class EvalDatasetBody(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: Optional[str] = None
    items: list[EvalDatasetItemBody] = Field(min_length=1)


class EvalRunBody(BaseModel):
    dataset_id: str
    score_name: str = Field(default="exact_match", min_length=1, max_length=128)


@router.get("/eval-datasets")
def list_datasets(auth: AuthContext = Depends(require_role("read_only"))):
    return [_dataset_dict(dataset, auth.db) for dataset in auth.db.query(EvalDataset).filter_by(project_id=auth.project_id).order_by(EvalDataset.created_at.desc()).all()]


@router.post("/eval-datasets")
def create_dataset(body: EvalDatasetBody, auth: AuthContext = Depends(require_role("editor"))):
    if auth.db.query(EvalDataset).filter_by(project_id=auth.project_id, name=body.name).first():
        raise HTTPException(status_code=409, detail="Eval dataset already exists")
    trace_ids = [item.trace_id for item in body.items]
    found_ids = {trace.id for trace in auth.db.query(Trace.id).filter(Trace.project_id == auth.project_id, Trace.id.in_(trace_ids)).all()}
    if missing := sorted(set(trace_ids) - found_ids):
        raise HTTPException(status_code=404, detail=f"Trace not found: {missing[0]}")
    dataset = EvalDataset(project_id=auth.project_id, name=body.name, description=body.description)
    auth.db.add(dataset)
    auth.db.flush()
    auth.db.add_all([EvalDatasetItem(dataset_id=dataset.id, trace_id=item.trace_id, expected_output=item.expected_output, metadata_field=item.metadata) for item in body.items])
    auth.db.commit()
    auth.db.refresh(dataset)
    return _dataset_dict(dataset, auth.db)


@router.get("/eval-runs")
def list_runs(dataset_id: Optional[str] = None, auth: AuthContext = Depends(require_role("read_only"))):
    query = auth.db.query(EvalRun).filter_by(project_id=auth.project_id)
    if dataset_id:
        query = query.filter(EvalRun.dataset_id == dataset_id)
    return [_run_dict(run, auth.db, include_results=False) for run in query.order_by(EvalRun.created_at.desc()).all()]


@router.get("/eval-runs/{run_id}")
def get_run(run_id: str, auth: AuthContext = Depends(require_role("read_only"))):
    run = auth.db.query(EvalRun).filter_by(id=run_id, project_id=auth.project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Eval run not found")
    return _run_dict(run, auth.db, include_results=True)


@router.post("/eval-runs")
def execute_run(body: EvalRunBody, auth: AuthContext = Depends(require_role("editor"))):
    dataset = auth.db.query(EvalDataset).filter_by(id=body.dataset_id, project_id=auth.project_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Eval dataset not found")
    items = auth.db.query(EvalDatasetItem).filter_by(dataset_id=dataset.id).order_by(EvalDatasetItem.created_at).all()
    run = EvalRun(project_id=auth.project_id, dataset_id=dataset.id, score_name=body.score_name, total_cases=len(items))
    auth.db.add(run)
    auth.db.flush()
    passed = 0
    for item in items:
        trace = auth.db.query(Trace).filter_by(id=item.trace_id, project_id=auth.project_id).one()
        value = float(_normalized(trace.output) == _normalized(item.expected_output))
        passed += int(value)
        score = Score(id=uuid.uuid4().hex, project_id=auth.project_id, trace_id=trace.id, name=body.score_name, data_type="NUMERIC", value=value, source="EVAL", comment=f"Eval run {run.id}")
        auth.db.add(score)
        auth.db.flush()
        auth.db.add(EvalRunResult(eval_run_id=run.id, dataset_item_id=item.id, trace_id=trace.id, actual_output=trace.output, value=value, score_id=score.id))
    run.passed_cases = passed
    run.average_score = passed / len(items) if items else None
    run.completed_at = datetime.now(timezone.utc)
    auth.db.commit()
    auth.db.refresh(run)
    return _run_dict(run, auth.db, include_results=True)


def _normalized(value: Any) -> str:
    if isinstance(value, str):
        return value.strip().casefold()
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _dataset_dict(dataset: EvalDataset, db) -> dict:
    items = db.query(EvalDatasetItem).filter_by(dataset_id=dataset.id).order_by(EvalDatasetItem.created_at).all()
    return {"id": dataset.id, "name": dataset.name, "description": dataset.description, "created_at": dataset.created_at.isoformat(), "items": [{"id": item.id, "trace_id": item.trace_id, "expected_output": item.expected_output, "metadata": item.metadata_field} for item in items]}


def _run_dict(run: EvalRun, db, include_results: bool) -> dict:
    payload = {"id": run.id, "dataset_id": run.dataset_id, "score_name": run.score_name, "status": run.status, "total_cases": run.total_cases, "passed_cases": run.passed_cases, "average_score": run.average_score, "aggregates": [{"name": run.score_name, "average": run.average_score, "count": run.total_cases}], "created_at": run.created_at.isoformat(), "completed_at": run.completed_at.isoformat() if run.completed_at else None}
    if include_results:
        results = db.query(EvalRunResult).filter_by(eval_run_id=run.id).order_by(EvalRunResult.created_at).all()
        payload["results"] = [{"id": result.id, "dataset_item_id": result.dataset_item_id, "trace_id": result.trace_id, "actual_output": result.actual_output, "value": result.value, "score_id": result.score_id} for result in results]
    return payload
