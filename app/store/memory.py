from __future__ import annotations

import copy
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

from app.llm.embeddings import cosine
from app.models import Chunk
from app.store.base import Row

DATA = Path(__file__).resolve().parent.parent.parent / "data"


def _now() -> str:
    return datetime.now(UTC).isoformat()


class MemoryStore:
    """Thread-safe in-memory adapter. Seeded from data/*.json. Mirrors PgStore semantics."""

    def __init__(self, seed: bool = True) -> None:
        self._lock = threading.RLock()
        self.equipment: dict[str, Row] = {}
        self.sensors: list[Row] = []
        self.failures: list[Row] = []
        self.chunks: dict[str, tuple[Chunk, list[float]]] = {}
        self.incidents: dict[str, Row] = {}
        self.runs: dict[str, Row] = {}
        self.observations: list[Row] = []
        self.hypotheses: list[Row] = []
        self.actions: dict[str, Row] = {}
        self.approvals: dict[str, Row] = {}
        self.audit: list[Row] = []
        self.policies: list[Row] = []
        if seed:
            self.equipment = {e["equipment_id"]: e for e in json.loads((DATA / "equipment/equipment.json").read_text())}
            self.sensors = json.loads((DATA / "sensors/readings.json").read_text())
            self.failures = json.loads((DATA / "history/failures.json").read_text())

    # -- master data
    def get_equipment(self, equipment_id):
        return copy.deepcopy(self.equipment.get(equipment_id))

    def latest_sensor_readings(self, equipment_id):
        rows = [s for s in self.sensors if s["equipment_id"] == equipment_id]
        by_sensor: dict[str, Row] = {}
        for r in sorted(rows, key=lambda s: (s["timestamp"], -int(s["reading_id"][3:]))):
            by_sensor[r["sensor"]] = r  # later timestamp wins; ties -> lowest reading_id wins
        return copy.deepcopy(list(by_sensor.values()))

    def list_failures(self, equipment_id, limit=10):
        return copy.deepcopy([f for f in self.failures if f["equipment_id"] == equipment_id][:limit])

    # -- rag
    def upsert_chunks(self, chunks):
        with self._lock:
            for c, emb in chunks:
                self.chunks[c.chunk_id] = (c, emb)
        return len(chunks)

    def search_chunks(self, embedding, plant_id, equipment_type, k, min_score):
        scored = []
        for c, emb in self.chunks.values():
            if c.plant_id not in (None, plant_id) or c.equipment_type not in (equipment_type, "all"):
                continue
            s = cosine(embedding, emb)
            if s >= min_score:
                scored.append(c.model_copy(update={"score": round(s, 4)}))
        return sorted(scored, key=lambda c: (-c.score, c.chunk_id))[:k]

    # -- incidents
    def get_incident(self, incident_id):
        return copy.deepcopy(self.incidents.get(incident_id))

    def create_incident(self, row):
        with self._lock:
            self.incidents.setdefault(row["incident_id"], {**row, "status": "open", "created_at": _now(), "updated_at": _now()})
            return copy.deepcopy(self.incidents[row["incident_id"]])

    def touch_incident(self, incident_id, status):
        with self._lock:
            self.incidents[incident_id].update(status=status, updated_at=_now())

    def add_run(self, row):
        with self._lock:
            self.runs[row["run_id"]] = {**row, "started_at": _now(), "finished_at": None, "steps": 0, "node_timings": {}}

    def finish_run(self, run_id, status, steps, node_timings):
        with self._lock:
            self.runs[run_id].update(status=status, steps=steps, node_timings=node_timings, finished_at=_now())

    def get_run(self, run_id):
        return copy.deepcopy(self.runs.get(run_id))

    def list_runs(self, incident_id):
        return copy.deepcopy([r for r in self.runs.values() if r["incident_id"] == incident_id])

    def add_observations(self, incident_id, run_id, user, rows):
        with self._lock:
            self.observations += [{**r, "incident_id": incident_id, "run_id": run_id, "created_by": user, "created_at": _now()} for r in rows]

    def list_observations(self, incident_id):
        return copy.deepcopy([o for o in self.observations if o["incident_id"] == incident_id])

    def add_hypotheses(self, incident_id, run_id, user, rows):
        with self._lock:
            self.hypotheses += [{**r, "incident_id": incident_id, "run_id": run_id, "created_by": user, "created_at": _now()} for r in rows]

    def list_hypotheses(self, incident_id):
        return copy.deepcopy([h for h in self.hypotheses if h["incident_id"] == incident_id])

    # -- actions
    def insert_action(self, row):
        with self._lock:
            for a in self.actions.values():
                if a["idempotency_key"] == row["idempotency_key"]:
                    return copy.deepcopy(a), False
            self.actions[row["action_id"]] = {**row, "created_at": _now(), "updated_at": _now(), "result": None}
            return copy.deepcopy(self.actions[row["action_id"]]), True

    def get_action(self, action_id):
        return copy.deepcopy(self.actions.get(action_id))

    def list_actions(self, incident_id):
        return copy.deepcopy([a for a in self.actions.values() if a["incident_id"] == incident_id])

    def transition_action(self, action_id, from_status, to_status, result=None):
        with self._lock:
            a = self.actions.get(action_id)
            if not a or a["status"] != from_status:
                return False
            a.update(status=to_status, updated_at=_now())
            if result is not None:
                a["result"] = result
            return True

    def insert_approval(self, row):
        with self._lock:
            self.approvals[row["approval_id"]] = {**row, "decided_by": None, "decided_at": None, "created_at": _now()}

    def get_approval(self, approval_id):
        return copy.deepcopy(self.approvals.get(approval_id))

    def approval_for_action(self, action_id):
        return copy.deepcopy(next((a for a in self.approvals.values() if a["action_id"] == action_id), None))

    def decide_approval(self, approval_id, from_status, to_status, decided_by):
        with self._lock:
            a = self.approvals.get(approval_id)
            if not a or a["status"] != from_status:
                return False
            a.update(status=to_status, decided_by=decided_by or a["decided_by"], decided_at=_now())
            return True

    # -- audit / policy
    def append_audit(self, row):
        with self._lock:
            self.audit.append({**row, "ts": _now()})

    def list_audit(self, incident_id):
        return copy.deepcopy([a for a in self.audit if a.get("incident_id") == incident_id])

    def save_policy_version(self, row):
        with self._lock:
            for p in self.policies:
                p["active"] = False
            self.policies.append({**row, "active": True, "created_at": _now()})

    def active_policy_version(self):
        return copy.deepcopy(next((p for p in reversed(self.policies) if p["active"]), None))

    def dump_json(self) -> str:  # debugging helper
        return json.dumps({"incidents": self.incidents}, default=str)
