from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_container, get_principal
from app.container import Container
from app.models import Principal

router = APIRouter()


@router.post("/approvals/{approval_id}/approve")
def approve(approval_id: str, p: Principal = Depends(get_principal), c: Container = Depends(get_container)) -> dict[str, Any]:
    return c.approvals.decide(p, approval_id, True)


@router.post("/approvals/{approval_id}/reject")
def reject(approval_id: str, p: Principal = Depends(get_principal), c: Container = Depends(get_container)) -> dict[str, Any]:
    return c.approvals.decide(p, approval_id, False)
