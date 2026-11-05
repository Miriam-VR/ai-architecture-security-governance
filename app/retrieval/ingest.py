"""Ingestion (V02): data/*.json -> chunks -> embeddings -> store. source_id is preserved on every chunk."""

from __future__ import annotations

import json
from pathlib import Path

from app.llm.embeddings import Embedder
from app.models import Chunk
from app.store.base import Store
from app.store.memory import DATA


def build_chunks(data_dir: Path = DATA) -> list[tuple[Chunk, str]]:
    """Return (chunk, text_to_embed). One chunk per failure; one per manual section / procedure."""
    out: list[tuple[Chunk, str]] = []
    for f in json.loads((data_dir / "history/failures.json").read_text()):
        text = (f"Falla {f['failure_id']} en {f['equipment_id']} ({f['equipment_type']}, {f['plant_id']}). Sintomas: {' '.join(f['symptoms'])}. "
                f"Causa confirmada: {f['confirmed_cause']} [{f['root_cause']}]. Acciones: {'; '.join(f['actions_taken'])}.")
        out.append((Chunk(chunk_id=f"{f['failure_id']}#0", source_id=f["failure_id"], source_type="failure", plant_id=f["plant_id"],
                          equipment_id=f["equipment_id"], equipment_type=f["equipment_type"], root_cause=f["root_cause"],
                          symptoms=f["symptoms"], text=text), f"{' '.join(f['symptoms'])} {f['equipment_type']}"))
    for m in json.loads((data_dir / "manuals/manuals.json").read_text()):
        for s in m["sections"]:
            out.append((Chunk(chunk_id=s["section_id"], source_id=s["section_id"], source_type="manual", equipment_type=m["equipment_type"],
                              text=s["text"]), f"{m['equipment_type']} {s['text']}"))
    for p in json.loads((data_dir / "procedures/procedures.json").read_text()):
        out.append((Chunk(chunk_id=p["procedure_id"], source_id=p["procedure_id"], source_type="procedure", equipment_type=p["equipment_type"],
                          text=p["text"]), f"{p['equipment_type']} {p['text']}"))
    return out


def ingest(store: Store, embedder: Embedder, data_dir: Path = DATA) -> int:
    pairs = [(c, embedder.embed(t)) for c, t in build_chunks(data_dir)]
    return store.upsert_chunks(pairs)
