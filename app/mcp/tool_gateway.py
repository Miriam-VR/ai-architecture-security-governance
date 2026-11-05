"""Tool Gateway (V03 -> V06 -> V08): the ONLY path from the agent to tools.

Order of checks (all deterministic, none depends on the LLM):
allowlist -> argument schema -> plant/role authorization -> authenticated MCP call -> typed result.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from app.governance.audit import AuditLog
from app.mcp import schemas as sc
from app.mcp.client import MCPClient, MCPError
from app.models import Principal
from app.security.authorization import TOOL_ROLES, authorize_tool
from app.security.errors import AccessDenied
from app.store.base import Store


class ToolRejected(Exception):
    def __init__(self, reason: str, code: str) -> None:
        super().__init__(reason)
        self.reason, self.code = reason, code


class ToolGateway:
    def __init__(self, client: MCPClient, store: Store, audit: AuditLog) -> None:
        self._client, self._store, self._audit = client, store, audit

    def list_tools(self, principal: Principal) -> list[str]:
        return [t["name"] for t in self._client.list_tools(principal) if principal.role in TOOL_ROLES.get(t["name"], ())]

    def call(self, principal: Principal, name: str, arguments: dict[str, Any], *, incident_id: str | None = None) -> BaseModel:
        try:
            result = self._call(principal, name, arguments)
        except ToolRejected as e:
            self._audit.record("tool_call", actor=principal.user_id, decision="denied", incident_id=incident_id,
                               details={"tool": name, "arguments": arguments, "code": e.code, "reason": e.reason})
            raise
        self._audit.record("tool_call", actor=principal.user_id, decision="allowed", incident_id=incident_id,
                           details={"tool": name, "arguments": arguments})
        return result

    def _call(self, principal: Principal, name: str, arguments: dict[str, Any]) -> BaseModel:
        if name not in sc.TOOL_ARGS or name not in TOOL_ROLES:
            raise ToolRejected(f"tool '{name}' is not in the allowlist", "not_allowlisted")
        try:
            parsed = sc.TOOL_ARGS[name](**arguments)
        except (ValidationError, TypeError) as e:
            raise ToolRejected(f"invalid arguments for '{name}': {str(e)[:120]}", "invalid_arguments") from e
        eq = self._store.get_equipment(parsed.equipment_id)  # type: ignore[attr-defined]
        if eq is None:
            raise ToolRejected("equipment not found", "not_found")
        try:
            authorize_tool(principal, name, plant_id=eq["plant_id"])
        except AccessDenied as e:
            raise ToolRejected(str(e), "forbidden") from e
        try:
            raw = self._client.call_tool(principal, name, parsed.model_dump())
        except MCPError as e:
            raise ToolRejected(e.message, f"mcp_{e.code}") from e
        return sc.TOOL_RESULTS[name](**raw)
