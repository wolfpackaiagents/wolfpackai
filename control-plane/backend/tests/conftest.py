"""Shared fixtures for AMP tests."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import main as app_main
from app.core.database import get_db
from app.core.config import get_settings
from app.models.entities import ApiKey, Base, Organization, Project


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(get_settings(), "provider_secrets_master_key", Fernet.generate_key().decode())
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    project_id = uuid.uuid4().hex[:32]

    with Session() as db:
        org = Organization(id=uuid.uuid4().hex[:32], name="Test Org")
        db.add(org)
        db.flush()
        proj = Project(id=project_id, organization_id=org.id, name="Test Proj")
        db.add(proj)
        db.flush()
        db.add(
            ApiKey(
                id="admin-key-00000000000000000000001",
                project_id=proj.id,
                public_key="pk-test",
                hashed_secret_key="ef260e9aa3c673af240d17a2660480361a8e081d1ffeca2a5ed0e3219fc18567",
                display_secret_key="dev",
                note="t",
                role="admin",
            )
        )
        db.add(
            ApiKey(
                project_id=proj.id,
                public_key="pk-read-only",
                hashed_secret_key="ef260e9aa3c673af240d17a2660480361a8e081d1ffeca2a5ed0e3219fc18567",
                display_secret_key="dev",
                note="read-only test key",
                role="read_only",
            )
        )
        db.add(
            ApiKey(
                project_id=proj.id,
                public_key="pk-editor",
                hashed_secret_key="ef260e9aa3c673af240d17a2660480361a8e081d1ffeca2a5ed0e3219fc18567",
                display_secret_key="dev",
                note="editor test key",
                role="editor",
            )
        )
        db.commit()

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app_main.app.dependency_overrides[get_db] = override_get_db
    previous_session_factory = app_main.app.state.ingestion_session_factory
    app_main.app.state.ingestion_session_factory = Session
    with TestClient(app_main.app) as c:
        c.session_factory = Session
        c.project_id = project_id
        yield c
    app_main.app.state.ingestion_session_factory = previous_session_factory
    app_main.app.dependency_overrides.clear()