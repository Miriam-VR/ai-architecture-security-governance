from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_container, get_principal
from app.container import Container
from app.models import DiagnoseRequest, DiagnosisResponse, Principal
from app.security.authorization import authorize
from app.services.diagnosis import DiagnosisService

router = APIRouter()


class IncidentCreate(BaseModel):
    incident_id: str = Field(pattern=r"^INC-[A-Za-z0-9-]{1,32}$")
    equipment_id: str
    plant_id: str
    symptoms: list[str] = Field(default_factory=list, max_length=20)


class IncidentDiagnose(BaseModel):
    symptoms: list[str] = Field(default_factory=list, max_length=20)
    message: str = Field(default="", max_length=2000)


@router.post("/incidents", status_code=201)
def create_incident(body: IncidentCreate, p: Principal = Depends(get_principal), c: Container = Depends(get_container)) -> dict[str, Any]:
    inc, resumed = c.memory.open_incident(p, DiagnoseRequest(**body.model_dump()))
    return {**inc, "already_existed": resumed}


@router.get("/incidents/{incident_id}")
def read_incident(incident_id: str, p: Principal = Depends(get_principal), c: Container = Depends(get_container)) -> dict[str, Any]:
    return c.memory.read_incident(p, incident_id)


@router.post("/incidents/{incident_id}/diagnose", response_model=DiagnosisResponse)
def diagnose_incident(incident_id: str, body: IncidentDiagnose, p: Principal = Depends(get_principal), c: Container = Depends(get_container)):
    inc = c.memory.read_incident(p, incident_id)  # scope check uses the STORED plant, not client input
    req = DiagnoseRequest(incident_id=incident_id, equipment_id=inc["equipment_id"], plant_id=inc["plant_id"],
                          symptoms=body.symptoms or inc["symptoms"], message=body.message)
    return DiagnosisService(c).diagnose(p, req, max_steps=c.settings.extended_max_steps)


@router.get("/runs/{run_id}")
def read_run(run_id: str, p: Principal = Depends(get_principal), c: Container = Depends(get_container)) -> dict[str, Any]:
    return c.memory.read_run(p, run_id)


@router.get("/incidents/{incident_id}/audit")
def read_audit(incident_id: str, p: Principal = Depends(get_principal), c: Container = Depends(get_container)) -> dict[str, Any]:
    inc = c.store.get_incident(incident_id)
    if inc is None:
        from app.security.errors import NotFound

        raise NotFound("incident not found")
    authorize(p, "audit:read", plant_id=inc["plant_id"])
    c.audit.record("audit_read", actor=p.user_id, incident_id=incident_id, decision="allowed")
    return {"incident_id": incident_id, "events": c.audit.for_incident(incident_id)}
