from __future__ import annotations

import itertools
from collections.abc import Callable
from typing import Any

from app.mcp.server import sign_envelope
from app.models import Principal


class MCPError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


class MCPClient:
    """Authenticated MCP client: signs the caller identity for every request."""

    def __init__(self, transport: Callable[[dict[str, Any]], dict[str, Any]], shared_secret: str) -> None:
        self._transport, self._secret, self._ids = transport, shared_secret, itertools.count(1)

    def _rpc(self, principal: Principal, method: str, params: dict[str, Any]) -> Any:
        req = {"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params,
               "meta": sign_envelope(self._secret, principal, method, params)}
        resp = self._transport(req)
        if "error" in resp:
            raise MCPError(resp["error"]["code"], resp["error"]["message"])
        return resp["result"]

    def list_tools(self, principal: Principal) -> list[dict[str, Any]]:
        return self._rpc(principal, "tools/list", {})["tools"]

    def call_tool(self, principal: Principal, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._rpc(principal, "tools/call", {"name": name, "arguments": arguments})
