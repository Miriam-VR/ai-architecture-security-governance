"""Embed failures/manuals/procedures and upsert them into the configured store (pgvector in Supabase).

IMPORTANT: ingest and query must use the SAME embedder. EMBEDDING_MODE=mock (offline) or openai.
Usage: python scripts/ingest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.llm.factory import build_embedder  # noqa: E402
from app.retrieval.ingest import ingest  # noqa: E402
from app.store.factory import build_store  # noqa: E402


def main() -> int:
    s = get_settings()
    n = ingest(build_store(s), build_embedder(s))
    print(f"ingested {n} chunks (store={s.store_mode}, embeddings={s.embedding_mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
