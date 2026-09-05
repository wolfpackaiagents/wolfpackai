"""Run a durable schedule locally without Inngest or an HTTP runtime.

    uv run python examples/local_schedule_demo.py
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.entities import Environment, EnvironmentRegistration, MeshDefinition, Organization, Project, Schedule
from app.services.schedule_runtime import ScheduleRuntime


def main() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        org = Organization(id="demo-org", name="Demo")
        project = Project(id="demo-project", organization_id=org.id, name="Demo")
        environment = Environment(id="demo-env", project_id=project.id, slug="local", name="Local")
        definition = MeshDefinition(id="demo-definition", project_id=project.id, key="demo", kind="agent", name="Demo", version="1")
        registration = EnvironmentRegistration(id="demo-registration", project_id=project.id, environment_id=environment.id, definition_id=definition.id)
        schedule = Schedule(id="demo-schedule", project_id=project.id, registration_id=registration.id, name="every-minute", schedule_type="interval", interval_seconds=60, next_run_at=datetime.now(timezone.utc) - timedelta(seconds=1), payload={"task": "demo"})
        db.add_all([org, project, environment, definition, registration, schedule])
        db.commit()
        ScheduleRuntime(db).dispatch_once(local_executor=lambda run: {"executed": run.payload["task"], "attempt": run.attempt})
        run = db.query(__import__("app.models.entities", fromlist=["ScheduledTaskRun"]).ScheduledTaskRun).one()
        print({"run_id": run.id, "status": run.status, "result": run.result})


if __name__ == "__main__":
    main()
