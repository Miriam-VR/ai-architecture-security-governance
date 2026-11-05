"""RBAC (role -> permissions) + ABAC (plant / equipment / incident attributes). Deterministic, outside the LLM."""

from __future__ import annotations

import os

from app.models import Principal
from app.security.errors import AccessDenied

_BASE = {"incident:create", "incident:read", "diagnose", "tool:read"}
PERMISSIONS: dict[str, frozenset[str]] = {
    "technician": frozenset(_BASE),
    "supervisor": frozenset(_BASE | {"approval:decide", "audit:read", "action:read"}),
    "administrator": frozenset(_BASE | {"approval:decide", "audit:read", "action:read", "policy:manage"}),
}

# tool -> roles allowed to call it (checked by the Tool Gateway AND again by the MCP server)
TOOL_ROLES: dict[str, frozenset[str]] = {
    "get_equipment_info": frozenset({"technician", "supervisor", "administrator"}),
    "get_sensor_readings": frozenset({"technician", "supervisor", "administrator"}),
    "get_failure_history": frozenset({"technician", "supervisor", "administrator"}),
}


def _fault_injected() -> bool:
    """V10 'break on purpose': lets CI prove the security suite detects a broken isolation check.
    Only honoured under pytest, so it can never be switched on in a deployed runtime."""
    return os.getenv("SIMULATE_ISOLATION_BUG") == "1" and "PYTEST_CURRENT_TEST" in os.environ


def authorize(p: Principal, permission: str, *, plant_id: str | None = None) -> None:
    if permission not in PERMISSIONS.get(p.role, frozenset()):
        raise AccessDenied(f"role '{p.role}' lacks permission '{permission}'")
    if plant_id is not None and not p.can_see_plant(plant_id) and not _fault_injected():
        raise AccessDenied("resource outside the caller's plant scope")


def authorize_tool(p: Principal, tool: str, *, plant_id: str | None) -> None:
    if p.role not in TOOL_ROLES.get(tool, frozenset()):
        raise AccessDenied(f"tool '{tool}' not permitted for role '{p.role}'")
    if plant_id is None or not p.can_see_plant(plant_id):
        raise AccessDenied("tool target outside the caller's plant scope")
