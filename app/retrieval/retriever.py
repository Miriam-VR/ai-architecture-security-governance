"""Scoped retriever (V02 + V07): plant/equipment filter is applied BEFORE similarity search."""

from __future__ import annotations

from app.llm.embeddings import Embedder
from app.models import Chunk, Principal
from app.security.authorization import authorize
from app.security.errors import AccessDenied, NotFound
from app.store.base import Store


class Retriever:
    def __init__(self, store: Store, embedder: Embedder, top_k: int = 5, min_score: float = 0.12) -> None:
        self._store, self._embedder, self._k, self._min = store, embedder, top_k, min_score

    def retrieve(self, principal: Principal, *, plant_id: str, equipment_id: str, symptoms: list[str]) -> list[Chunk]:
        authorize(principal, "diagnose", plant_id=plant_id)  # scope door #1 (RAG)
        eq = self._store.get_equipment(equipment_id)
        if eq is None:
            raise NotFound("equipment not found")
        if eq["plant_id"] != plant_id:
            raise AccessDenied("equipment does not belong to the requested plant")
        query = f"{' '.join(symptoms)} {eq['type']}"
        found = self._store.search_chunks(self._embedder.embed(query), plant_id, eq["type"], self._k, self._min)
        return [c for c in found if c.plant_id in (None, plant_id)]  # defence in depth: never trust the adapter alone
