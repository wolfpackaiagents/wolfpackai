"""Admin routes: manage projects and API keys. Protected by X-Admin-Key."""

from __future__ import annotations

from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.auth import generate_api_key, require_admin
from ..core.database import get_db
from ..models.entities import ApiKey, Organization, Project

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


class OrgCreate(BaseModel):
    name: str


class OrgOut(BaseModel):
    id: str
    name: str


class ProjectCreate(BaseModel):
    organization_id: str
    name: str


class ProjectOut(BaseModel):
    id: str
    organization_id: str
    name: str


class ApiKeyCreate(BaseModel):
    project_id: str
    note: str = ""
    role: Literal["read_only", "editor", "admin"] = "editor"


class ApiKeyOut(BaseModel):
    id: str
    project_id: str
    public_key: str
    secret_key: str
    note: str = ""
    role: str


@router.get("/organizations", response_model=List[OrgOut])
def list_orgs(db: Session = Depends(get_db)):
    return db.query(Organization).all()


@router.post("/organizations", response_model=OrgOut)
def create_org(body: OrgCreate, db: Session = Depends(get_db)):
    org = Organization(name=body.name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return OrgOut(id=org.id, name=org.name)


@router.post("/projects", response_model=ProjectOut)
def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    if not db.get(Organization, body.organization_id):
        raise HTTPException(status_code=404, detail="Organización no encontrada")
    p = Project(organization_id=body.organization_id, name=body.name)
    db.add(p)
    db.commit()
    db.refresh(p)
    return ProjectOut(id=p.id, organization_id=p.organization_id, name=p.name)


@router.get("/projects", response_model=List[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).all()


@router.post("/api-keys", response_model=ApiKeyOut)
def create_api_key(body: ApiKeyCreate, db: Session = Depends(get_db)):
    if not db.get(Project, body.project_id):
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    public, secret, hashed = generate_api_key()
    key = ApiKey(
        project_id=body.project_id,
        public_key=public,
        hashed_secret_key=hashed,
        display_secret_key=secret[:6] + "..." + secret[-4:],
        note=body.note,
        role=body.role,
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return ApiKeyOut(id=key.id, project_id=key.project_id, public_key=key.public_key, secret_key=f"{public}:{secret}", role=key.role)
