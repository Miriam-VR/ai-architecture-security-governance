"""Supabase Postgres adapter (psycopg2). Uses the pooled DATABASE_URL.

Lambda note: use the *transaction* pooler (port 6543) and keep DB_POOL_MAX small, because every
warm Lambda container holds its own connection(s). Prepared statements are not used (pooler-safe).
"""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

from app.models import Chunk
from app.store.base import Row


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


class PgStore:
    def __init__(self, dsn: str, pool_max: int = 2) -> None:
        if not dsn:
            raise RuntimeError("DATABASE_URL missing (STORE_MODE=supabase)")
        self._pool = ThreadedConnectionPool(1, max(pool_max, 1), dsn)
        self._lock = threading.Lock()

    @contextmanager
    def _cur(self):
        conn = self._pool.getconn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def _all(self, sql: str, args: tuple = ()) -> list[Row]:
        with self._cur() as cur:
            cur.execute(sql, args)
            return [dict(r) for r in cur.fetchall()]

    def _one(self, sql: str, args: tuple = ()) -> Row | None:
        rows = self._all(sql, args)
        return rows[0] if rows else None

    def _exec(self, sql: str, args: tuple = ()) -> int:
        with self._cur() as cur:
            cur.execute(sql, args)
            return cur.rowcount

    # -- master data
    def get_equipment(self, equipment_id):
        r = self._one("select equipment_id, plant_id, type, model, criticality, location, next_maintenance::text from equipment where equipment_id=%s", (equipment_id,))
        return r

    def latest_sensor_readings(self, equipment_id):
        return self._all(
            "select distinct on (sensor) reading_id, equipment_id, sensor, value, unit, quality, read_at::text as timestamp "
            "from sensor_readings where equipment_id=%s order by sensor, read_at desc, reading_id", (equipment_id,))

    def list_failures(self, equipment_id, limit=10):
        return self._all(
            "select failure_id, plant_id, equipment_id, equipment_type, occurred_on::text as date, symptoms, root_cause, confirmed_cause, "
            "actions_taken, refs as references from failure_history where equipment_id=%s order by occurred_on desc limit %s", (equipment_id, limit))

    # -- rag
    def upsert_chunks(self, chunks):
        with self._cur() as cur:
            for c, emb in chunks:
                cur.execute(
                    "insert into failure_history_chunks(chunk_id,source_id,source_type,plant_id,equipment_id,equipment_type,root_cause,symptoms,text,embedding) "
                    "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector) on conflict (chunk_id) do update set text=excluded.text, "
                    "embedding=excluded.embedding, symptoms=excluded.symptoms, root_cause=excluded.root_cause",
                    (c.chunk_id, c.source_id, c.source_type, c.plant_id, c.equipment_id, c.equipment_type, c.root_cause, c.symptoms, c.text, _vec(emb)))
        return len(chunks)

    def search_chunks(self, embedding, plant_id, equipment_type, k, min_score):
        v = _vec(embedding)
        rows = self._all(
            "select chunk_id, source_id, source_type, plant_id, equipment_id, equipment_type, root_cause, symptoms, text, "
            "1 - (embedding <=> %s::vector) as score from failure_history_chunks "
            "where (plant_id = %s or plant_id is null) and equipment_type in (%s, 'all') "
            "order by embedding <=> %s::vector limit %s", (v, plant_id, equipment_type, v, k))
        return [Chunk(**{**r, "score": round(float(r["score"]), 4)}) for r in rows if float(r["score"]) >= min_score]

    # -- incidents
    def get_incident(self, incident_id):
        return self._one("select incident_id, plant_id, equipment_id, status, symptoms, created_by, created_at::text, updated_at::text from incidents where incident_id=%s", (incident_id,))

    def create_incident(self, row):
        self._exec("insert into incidents(incident_id,plant_id,equipment_id,symptoms,created_by) values (%s,%s,%s,%s,%s) on conflict (incident_id) do nothing",
                   (row["incident_id"], row["plant_id"], row["equipment_id"], row.get("symptoms", []), row["created_by"]))
        return self.get_incident(row["incident_id"])  # type: ignore[return-value]

    def touch_incident(self, incident_id, status):
        self._exec("update incidents set status=%s, updated_at=now() where incident_id=%s", (status, incident_id))

    def add_run(self, row):
        self._exec("insert into agent_runs(run_id,incident_id,trace_id,status,created_by) values (%s,%s,%s,%s,%s)",
                   (row["run_id"], row["incident_id"], row["trace_id"], row["status"], row["created_by"]))

    def finish_run(self, run_id, status, steps, node_timings):
        self._exec("update agent_runs set status=%s, steps=%s, node_timings=%s, finished_at=now() where run_id=%s",
                   (status, steps, json.dumps(node_timings), run_id))

    def get_run(self, run_id):
        return self._one("select run_id, incident_id, trace_id, status, steps, node_timings, created_by from agent_runs where run_id=%s", (run_id,))

    def list_runs(self, incident_id):
        return self._all("select run_id, incident_id, trace_id, status, steps, created_by from agent_runs where incident_id=%s order by started_at", (incident_id,))

    def add_observations(self, incident_id, run_id, user, rows):
        with self._cur() as cur:
            for r in rows:
                cur.execute("insert into observations(incident_id,run_id,equipment_id,name,value,unit,source,created_by) values (%s,%s,%s,%s,%s,%s,%s,%s)",
                            (incident_id, run_id, r["equipment_id"], r["name"], str(r["value"]), r.get("unit", ""), r["source"], user))

    def list_observations(self, incident_id):
        return self._all("select incident_id, run_id, equipment_id, name, value, unit, source from observations where incident_id=%s order by created_at", (incident_id,))

    def add_hypotheses(self, incident_id, run_id, user, rows):
        with self._cur() as cur:
            for r in rows:
                cur.execute("insert into hypotheses(incident_id,run_id,cause,confidence,evidence_ids,rationale,created_by) values (%s,%s,%s,%s,%s,%s,%s)",
                            (incident_id, run_id, r["cause"], r["confidence"], r.get("evidence_ids", []), r.get("rationale", ""), user))

    def list_hypotheses(self, incident_id):
        rows = self._all("select incident_id, run_id, cause, confidence, evidence_ids, rationale from hypotheses where incident_id=%s order by created_at", (incident_id,))
        return [{**r, "confidence": float(r["confidence"])} for r in rows]

    # -- actions
    _ACTION_COLS = "action_id, incident_id, plant_id, run_id, action_type, params, risk, status, idempotency_key, policy_version, result, created_by"

    def insert_action(self, row):
        n = self._exec(
            "insert into action_requests(action_id,incident_id,plant_id,run_id,action_type,params,risk,status,idempotency_key,policy_version,created_by) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict (idempotency_key) do nothing",
            (row["action_id"], row["incident_id"], row["plant_id"], row.get("run_id"), row["action_type"], json.dumps(row["params"]), row["risk"],
             row["status"], row["idempotency_key"], row["policy_version"], row["created_by"]))
        existing = self._one(f"select {self._ACTION_COLS} from action_requests where idempotency_key=%s", (row["idempotency_key"],))
        return existing, n == 1  # type: ignore[return-value]

    def get_action(self, action_id):
        return self._one(f"select {self._ACTION_COLS} from action_requests where action_id=%s", (action_id,))

    def list_actions(self, incident_id):
        return self._all(f"select {self._ACTION_COLS} from action_requests where incident_id=%s order by created_at", (incident_id,))

    def transition_action(self, action_id, from_status, to_status, result=None):
        n = self._exec("update action_requests set status=%s, updated_at=now(), result=coalesce(%s::jsonb, result), "
                       "executed_at=case when %s='executed' then now() else executed_at end where action_id=%s and status=%s",
                       (to_status, json.dumps(result) if result is not None else None, to_status, action_id, from_status))
        return n == 1

    def insert_approval(self, row):
        self._exec("insert into approvals(approval_id,action_id,status,action_hash,expires_at,created_by) values (%s,%s,%s,%s,%s,%s)",
                   (row["approval_id"], row["action_id"], row["status"], row["action_hash"], row["expires_at"], row["created_by"]))

    def get_approval(self, approval_id):
        return self._one("select approval_id, action_id, status, action_hash, expires_at::text, decided_by, created_by from approvals where approval_id=%s", (approval_id,))

    def approval_for_action(self, action_id):
        return self._one("select approval_id, action_id, status, action_hash, expires_at::text, decided_by, created_by from approvals where action_id=%s order by created_at desc limit 1", (action_id,))

    def decide_approval(self, approval_id, from_status, to_status, decided_by):
        n = self._exec("update approvals set status=%s, decided_by=coalesce(%s, decided_by), decided_at=now() where approval_id=%s and status=%s",
                       (to_status, decided_by, approval_id, from_status))
        return n == 1

    # -- audit / policy
    def append_audit(self, row):
        self._exec("insert into audit_events(event_id,event_type,incident_id,run_id,trace_id,actor,decision,details) values (%s,%s,%s,%s,%s,%s,%s,%s)",
                   (row["event_id"], row["event_type"], row.get("incident_id"), row.get("run_id"), row.get("trace_id"), row["actor"],
                    row.get("decision"), json.dumps(row.get("details", {}), default=str)))

    def list_audit(self, incident_id):
        return self._all("select event_id, ts::text, event_type, incident_id, run_id, trace_id, actor, decision, details from audit_events where incident_id=%s order by ts, id", (incident_id,))

    def save_policy_version(self, row):
        with self._cur() as cur:
            cur.execute("update policy_versions set active=false where active")
            cur.execute("insert into policy_versions(version,rules,rules_hash,active,created_by) values (%s,%s,%s,true,%s)",
                        (row["version"], json.dumps(row["rules"]), row["rules_hash"], row["created_by"]))

    def active_policy_version(self):
        r = self._one("select version, rules, rules_hash, created_by from policy_versions where active order by created_at desc limit 1")
        return r

    def close(self) -> None:
        self._pool.closeall()


