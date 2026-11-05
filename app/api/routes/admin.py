from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_container, get_principal
from app.container import Container
from app.models import Principal
from app.security.authorization import authorize

router = APIRouter(prefix="/admin")


class PolicyChange(BaseModel):
    version: str = Field(pattern=r"^policy-[A-Za-z0-9.\-]{1,32}$")
    rules: dict[str, dict[str, Any]]


@router.get("/policy")
def current_policy(p: Principal = Depends(get_principal), c: Container = Depends(get_container)) -> dict[str, Any]:
    authorize(p, "policy:manage")
    return {"version": c.policy.version, "rules": c.policy.rules}


@router.post("/policy")
def change_policy(body: PolicyChange, p: Principal = Depends(get_principal), c: Container = Depends(get_container)) -> dict[str, Any]:
    authorize(p, "policy:manage")
    c.policy.activate(body.rules, body.version, p.user_id)
    return {"version": c.policy.version}
