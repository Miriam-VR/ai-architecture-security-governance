from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container, get_principal
from app.container import Container
from app.models import DiagnoseRequest, DiagnosisResponse, Principal
from app.services.diagnosis import DiagnosisService

router = APIRouter()


@router.post("/diagnose", response_model=DiagnosisResponse)
def diagnose(req: DiagnoseRequest, p: Principal = Depends(get_principal), c: Container = Depends(get_container)):
    return DiagnosisService(c).diagnose(p, req, max_steps=c.settings.quick_max_steps)


@router.post("/diagnose/quick", response_model=DiagnosisResponse)
def diagnose_quick(req: DiagnoseRequest, p: Principal = Depends(get_principal), c: Container = Depends(get_container)):
    """Short, bursty queries -> Lambda route."""
    return DiagnosisService(c).diagnose(p, req, max_steps=c.settings.quick_max_steps)


@router.post("/diagnose/extended", response_model=DiagnosisResponse)
def diagnose_extended(req: DiagnoseRequest, p: Principal = Depends(get_principal), c: Container = Depends(get_container)):
    """More reasoning steps -> EC2 route (same code, explicit API Gateway route)."""
    return DiagnosisService(c).diagnose(p, req, max_steps=c.settings.extended_max_steps)
