from __future__ import annotations

from app.config import Settings
from app.store.base import Store
from app.store.memory import MemoryStore


def build_store(s: Settings) -> Store:
    if s.store_mode == "supabase":
        from app.store.postgres import PgStore

        return PgStore(s.database_url, s.db_pool_max)
    return MemoryStore()
