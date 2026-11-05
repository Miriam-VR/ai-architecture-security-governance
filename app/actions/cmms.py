"""SIMULATED CMMS. No real system is ever contacted; idempotent by key (second line of defence)."""

from __future__ import annotations

import threading
from typing import Any

from app.observability.telemetry import new_id


class MockCMMS:
    def __init__(self) -> None:
        self.work_orders: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_work_order(self, idempotency_key: str, mode: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if idempotency_key in self.work_orders:
                return self.work_orders[idempotency_key]
            wo = {"work_order_id": new_id("WO"), "mode": mode, "payload": payload, "simulated": True}
            self.work_orders[idempotency_key] = wo
            return wo
