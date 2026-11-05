"""Maintenance MCP server (JSON-RPC 2.0 shaped: tools/list, tools/call).

Server-side authorization (V08): the server does NOT trust the client gateway. It verifies the HMAC
signature of the caller identity, re-validates the tool allowlist + argument schema, and re-resolves
the equipment's plant from the store before answering. Read-only: no tool can change equipment state.

Transport here is in-process (deterministic tests). The same handler can be mounted behind HTTP/SSE
on EC2 for a persistent remote MCP server.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

from pydantic import ValidationError

from app.mcp import schemas as sc
from app.models import Principal
from app.security.authorization import authorize_tool
from app.security.errors import AccessDenied
from app.store.base import Store

E_METHOD, E_PARAMS, E_FORBIDDEN, E_UNAUTH, E_NOTFOUND = -32601, -32602, -32001, -32002, -32004
MAX_SKEW_S = 60


def sign_envelope(secret: str, principal: Principal, method: str, params: dict[str, Any], ts: int | None = None) -> dict[str, Any]:
    ts = ts or int(time.time())
    body = json.dumps({"p": principal.model_dump(mode="json"), "m": method, "a": params, "ts": ts}, sort_keys=True)
    sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return {"principal": principal.model_dump(mode="json"), "ts": ts, "sig": sig}


class MaintenanceMCPServer:
    def __init__(self, store: Store, shared_secret: str) -> None:
        if not shared_secret:
            raise RuntimeError("MCP_SHARED_SECRET required")
        self._store, self._secret = store, shared_secret

    def _err(self, rid: Any, code: int, msg: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}

    def _authenticate(self, req: dict[str, Any]) -> Principal | None:
        meta = req.get("meta") or {}
        try:
            expected = sign_envelope(self._secret, Principal(**meta["principal"]), req["method"], req.get("params", {}), int(meta["ts"]))
        except (KeyError, TypeError, ValueError, ValidationError):
            return None
        if not hmac.compare_digest(expected["sig"], str(meta.get("sig", ""))) or abs(time.time() - int(meta["ts"])) > MAX_SKEW_S:
            return None
        return Principal(**meta["principal"])

    def handle(self, req: dict[str, Any]) -> dict[str, Any]:
        rid = req.get("id")
        principal = self._authenticate(req)
        if principal is None:
            return self._err(rid, E_UNAUTH, "unauthenticated MCP caller")
        method, params = req.get("method"), req.get("params", {})
        if method == "tools/list":
            tools = [{"name": n, "description": sc.TOOL_DESCRIPTIONS[n], "inputSchema": m.model_json_schema()} for n, m in sc.TOOL_ARGS.items()]
            return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tools}}
        if method != "tools/call":
            return self._err(rid, E_METHOD, "method not found")
        name, args = params.get("name"), params.get("arguments", {})
        if name not in sc.TOOL_ARGS:  # allowlist, enforced AGAIN server-side
            return self._err(rid, E_METHOD, f"unknown tool '{name}'")
        try:
            parsed = sc.TOOL_ARGS[name](**args)
        except (ValidationError, TypeError) as e:
            return self._err(rid, E_PARAMS, f"invalid arguments: {str(e)[:160]}")
        eq = self._store.get_equipment(parsed.equipment_id)  # type: ignore[attr-defined]
        if eq is None:
            return self._err(rid, E_NOTFOUND, "equipment not found")
        try:
            authorize_tool(principal, name, plant_id=eq["plant_id"])
        except AccessDenied as e:
            return self._err(rid, E_FORBIDDEN, str(e))
        return {"jsonrpc": "2.0", "id": rid, "result": self._run(name, parsed, eq)}

    def _run(self, name: str, args: Any, eq: dict[str, Any]) -> dict[str, Any]:
        if name == "get_equipment_info":
            return sc.EquipmentInfo(**{k: eq[k] for k in sc.EquipmentInfo.model_fields if k in eq}).model_dump()
        if name == "get_sensor_readings":
            rows = self._store.latest_sensor_readings(args.equipment_id)
            return sc.SensorReadings(equipment_id=args.equipment_id, readings=[sc.SensorReading(**{k: r[k] for k in sc.SensorReading.model_fields}) for r in rows]).model_dump()
        rows = self._store.list_failures(args.equipment_id, args.limit)
        return sc.FailureHistory(equipment_id=args.equipment_id, failures=[sc.FailureRecord(**{k: r[k] for k in sc.FailureRecord.model_fields}) for r in rows]).model_dump()
