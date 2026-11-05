"""Embedders. The hash embedder is deterministic and offline (tests, workshop without OpenAI)."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import httpx

_TOKEN = re.compile(r"[a-z0-9_]+")


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Bag-of-tokens hashed into `dim` buckets, L2-normalised. Similarity == lexical overlap."""

    def __init__(self, dim: int = 1536) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _TOKEN.findall(text.lower()):
            if len(tok) < 4 and "_" not in tok:
                continue
            idx = int.from_bytes(hashlib.sha1(tok.encode()).digest()[:4], "big") % self.dim  # noqa: S324
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str, dim: int = 1536, timeout: float = 20.0,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.dim, self._model = dim, model
        self._client = httpx.Client(base_url="https://api.openai.com/v1", timeout=timeout, transport=transport,
                                    headers={"Authorization": f"Bearer {api_key}"})

    def embed(self, text: str) -> list[float]:
        r = self._client.post("/embeddings", json={"model": self._model, "input": text})
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))
