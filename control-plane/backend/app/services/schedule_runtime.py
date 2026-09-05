"""Durable schedule materialization, leasing, and safe local/HTTP dispatch."""

from __future__ import annotations

import ipaddress
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..models.entities import EnvironmentRegistration, RegistrationHeartbeat, RuntimeReplica, Schedule, ScheduledTaskRun
from .scheduling import next_run_at, occurrence_key
from .schedule_observability import SCHEDULE_RETRIES, SCHEDULE_RUNS, record_terminal_failure


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class ScheduleRuntime:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def materialize_due(self, limit: int = 100, now: datetime | None = None) -> list[str]:
        now = now or utcnow()
        query = self.db.query(Schedule).filter(Schedule.status == "active", Schedule.next_run_at <= now).order_by(Schedule.next_run_at)
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        schedules = query.limit(limit).all()
        created: list[str] = []
        for schedule in schedules:
            scheduled_for = _utc(schedule.next_run_at)
            lateness = (now - scheduled_for).total_seconds()
            if lateness <= schedule.misfire_grace_seconds or schedule.misfire_policy == "fire_once":
                key = occurrence_key("scheduled", scheduled_for)
                run = ScheduledTaskRun(
                    project_id=schedule.project_id, schedule_id=schedule.id, registration_id=schedule.registration_id,
                    occurrence_key=key, trigger="scheduled", status="pending", scheduled_for=scheduled_for,
                    max_attempts=schedule.max_attempts, payload=schedule.payload or {},
                    deadline_at=scheduled_for + timedelta(seconds=self.settings.scheduler_deadline_seconds),
                )
                # The unique occurrence constraint is the cross-worker idempotency gate.
                try:
                    with self.db.begin_nested():
                        self.db.add(run)
                        self.db.flush()
                    created.append(run.id)
                except Exception:
                    # Another scheduler materialized the same occurrence.
                    pass
            schedule.last_run_at = scheduled_for
            schedule.next_run_at = next_run_at(schedule.schedule_type, now, at=schedule.at, interval_seconds=schedule.interval_seconds, cron=schedule.cron, timezone_name=schedule.timezone)
            if schedule.next_run_at is None:
                schedule.status = "completed"
        self.db.commit()
        return created

    def claim(self, worker_id: str, limit: int = 1, now: datetime | None = None, project_id: str | None = None) -> list[ScheduledTaskRun]:
        now = now or utcnow()
        expired_query = self.db.query(ScheduledTaskRun).filter(ScheduledTaskRun.status == "running", ScheduledTaskRun.lease_expires_at < now)
        if project_id:
            expired_query = expired_query.filter(ScheduledTaskRun.project_id == project_id)
        expired = expired_query.all()
        for run in expired:
            self._fail_or_retry(run, "lease expired", now)
        self.db.flush()
        eligible = or_(
            and_(ScheduledTaskRun.status == "pending", ScheduledTaskRun.scheduled_for <= now),
            and_(ScheduledTaskRun.status == "retrying", ScheduledTaskRun.retry_at <= now),
        )
        query = self.db.query(ScheduledTaskRun).filter(eligible).order_by(ScheduledTaskRun.scheduled_for)
        if project_id:
            query = query.filter(ScheduledTaskRun.project_id == project_id)
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        runs = query.limit(limit).all()
        claimed = []
        for run in runs:
            if run.deadline_at and _utc(run.deadline_at) <= now:
                run.status, run.error, run.completed_at = "deadline_exceeded", "run deadline exceeded before claim", now
                SCHEDULE_RUNS.labels("deadline_exceeded").inc()
                record_terminal_failure(self.db, run)
                continue
            run.status = "running"
            run.attempt += 1
            run.fencing_token += 1
            run.claimed_by = worker_id
            run.started_at = now
            run.lease_expires_at = now + timedelta(seconds=self.settings.scheduler_lease_seconds)
            claimed.append(run)
        self.db.commit()
        return claimed

    def complete(self, run_id: str, fencing_token: int, result: dict | None = None) -> ScheduledTaskRun | None:
        run = self.db.get(ScheduledTaskRun, run_id)
        if not run:
            return None
        if run.status == "succeeded" and run.fencing_token == fencing_token:
            return run
        if run.status != "running" or run.fencing_token != fencing_token or (run.lease_expires_at and _utc(run.lease_expires_at) < utcnow()):
            raise ValueError("stale run claim")
        trace_id = result.get("trace_id") if isinstance(result, dict) else None
        if isinstance(trace_id, str) and trace_id:
            run.trace_id = trace_id
        run.status, run.result, run.completed_at, run.lease_expires_at = "succeeded", result, utcnow(), None
        SCHEDULE_RUNS.labels("succeeded").inc()
        self.db.commit()
        return run

    def fail(self, run_id: str, fencing_token: int, error: str) -> ScheduledTaskRun | None:
        run = self.db.get(ScheduledTaskRun, run_id)
        if not run:
            return None
        if run.status in {"failed", "deadline_exceeded"} and run.fencing_token == fencing_token:
            return run
        if run.status != "running" or run.fencing_token != fencing_token:
            raise ValueError("stale run claim")
        self._fail_or_retry(run, error, utcnow())
        self.db.commit()
        return run

    def renew_lease(self, run_id: str, fencing_token: int, worker_id: str) -> ScheduledTaskRun | None:
        run = self.db.get(ScheduledTaskRun, run_id)
        if not run:
            return None
        now = utcnow()
        if run.status != "running" or run.fencing_token != fencing_token or run.claimed_by != worker_id or (run.lease_expires_at and _utc(run.lease_expires_at) <= now):
            raise ValueError("stale run claim")
        run.lease_expires_at = now + timedelta(seconds=self.settings.scheduler_lease_seconds)
        self.db.commit()
        return run

    def cancel(self, run_id: str, fencing_token: int | None = None) -> ScheduledTaskRun | None:
        run = self.db.get(ScheduledTaskRun, run_id)
        if not run:
            return None
        if run.status in {"succeeded", "failed", "deadline_exceeded", "cancelled"}:
            return run
        if fencing_token is not None and (run.status != "running" or run.fencing_token != fencing_token):
            raise ValueError("stale run claim")
        run.status, run.completed_at, run.lease_expires_at = "cancelled", utcnow(), None
        self.db.commit()
        return run

    def _fail_or_retry(self, run: ScheduledTaskRun, error: str, now: datetime) -> None:
        run.error, run.lease_expires_at = error[:4000], None
        if run.deadline_at and _utc(run.deadline_at) <= now:
            run.status, run.completed_at = "deadline_exceeded", now
            SCHEDULE_RUNS.labels("deadline_exceeded").inc()
            record_terminal_failure(self.db, run)
        elif run.attempt >= run.max_attempts:
            run.status, run.completed_at = "failed", now
            SCHEDULE_RUNS.labels("failed").inc()
            record_terminal_failure(self.db, run)
        else:
            schedule = self.db.get(Schedule, run.schedule_id)
            run.status = "retrying"
            run.retry_at = now + timedelta(seconds=schedule.retry_delay_seconds if schedule else 60)
            SCHEDULE_RETRIES.inc()

    def dispatch_once(self, worker_id: str = "scheduler", local_executor=None) -> int:
        self.materialize_due()
        runs = self.claim(worker_id, limit=20)
        for run in runs:
            try:
                if local_executor is not None:
                    result = local_executor(run)
                    self.complete(run.id, run.fencing_token, result or {})
                else:
                    self._dispatch_http(run)
            except Exception as error:
                self.fail(run.id, run.fencing_token, str(error))
        return len(runs)

    def _dispatch_http(self, run: ScheduledTaskRun) -> None:
        registration = self.db.get(EnvironmentRegistration, run.registration_id)
        if not registration or not registration.enabled:
            raise RuntimeError("registration is unavailable")
        cutoff = utcnow() - timedelta(seconds=self.settings.mesh_heartbeat_ttl_seconds)
        replicas = self.db.query(RuntimeReplica, RegistrationHeartbeat).join(
            RegistrationHeartbeat,
            and_(RegistrationHeartbeat.registration_id == RuntimeReplica.registration_id, RegistrationHeartbeat.instance_id == RuntimeReplica.instance_id),
        ).filter(
            RuntimeReplica.registration_id == run.registration_id,
            RuntimeReplica.enabled.is_(True),
            RegistrationHeartbeat.last_seen >= cutoff,
        ).all()
        candidates = []
        for replica, heartbeat in replicas:
            if not self._safe_endpoint(replica.endpoint):
                continue
            load = self.db.query(ScheduledTaskRun).filter(
                ScheduledTaskRun.registration_id == run.registration_id,
                ScheduledTaskRun.status == "running",
                ScheduledTaskRun.claimed_by == replica.instance_id,
            ).count()
            if load < replica.capacity:
                candidates.append((load, replica.instance_id, replica, heartbeat))
        if candidates:
            _, _, replica, heartbeat = min(candidates, key=lambda item: (item[0] / item[2].capacity, item[0], item[1]))
            endpoint, instance_id = replica.endpoint, replica.instance_id
        elif replicas:
            raise RuntimeError("no live runtime replica with available capacity")
        else:
            # Existing registrations retain their administratively configured endpoint.
            endpoint = registration.schedule_endpoint
            heartbeat = self.db.query(RegistrationHeartbeat).filter(
                RegistrationHeartbeat.registration_id == run.registration_id,
                RegistrationHeartbeat.last_seen >= cutoff,
            ).order_by(RegistrationHeartbeat.last_seen.desc(), RegistrationHeartbeat.instance_id).first()
            if not heartbeat or not endpoint or not self._safe_endpoint(endpoint):
                raise RuntimeError("no live runtime replica")
            instance_id = heartbeat.instance_id
        run.claimed_by = instance_id
        self.db.commit()
        payload = {
            "run_id": run.id,
            "schedule_id": run.schedule_id,
            "fencing_token": run.fencing_token,
            "attempt": run.attempt,
            "target_instance_id": instance_id,
            "payload": run.payload,
            "deadline_at": run.deadline_at.isoformat() if run.deadline_at else None,
        }
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        if not self.settings.scheduler_dispatch_secret:
            raise RuntimeError("scheduler_dispatch_secret is required for HTTP dispatch")
        signature = hmac.new(self.settings.scheduler_dispatch_secret.encode(), body, hashlib.sha256).hexdigest()
        with httpx.Client(timeout=10.0) as client:
            response = client.post(endpoint, content=body, headers={"Content-Type": "application/json", "X-Wolfpack-Schedule-Signature": f"sha256={signature}"})
            response.raise_for_status()

    def _safe_endpoint(self, endpoint: str) -> bool:
        return safe_endpoint(endpoint, self.settings)


def safe_endpoint(endpoint: str, settings) -> bool:
    """Validate endpoint against SSRF protection rules.

    Production: HTTPS only, hostname must be in scheduler_http_allowed_hosts.
    Dev fallback: scheduler_allow_insecure_http permits HTTP loopback/localhost.
    """
    parsed = urlparse(endpoint)
    if parsed.scheme == "https" and parsed.hostname:
        allowed = {host.strip().lower() for host in settings.scheduler_http_allowed_hosts.split(",") if host.strip()}
        return bool(allowed) and parsed.hostname.lower() in allowed
    if not settings.scheduler_allow_insecure_http or parsed.scheme != "http" or not parsed.hostname:
        return False
    try:
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        return parsed.hostname == "localhost"


def verify_schedule_callback(secret: str, body: bytes, signature: str | None) -> bool:
    """Verify the callback HMAC over the exact request body."""
    if not secret or not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.removeprefix("sha256="))
