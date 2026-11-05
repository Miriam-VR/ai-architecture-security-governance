from __future__ import annotations

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.embeddings import Embedder, HashEmbedder, OpenAIEmbedder
from app.llm.mock_provider import MockLLM
from app.llm.openai_provider import OpenAIProvider


def build_llm(s: Settings) -> LLMProvider:
    if s.llm_mode == "openai":
        return OpenAIProvider(s.openai_api_key, s.openai_model, s.openai_timeout_s)
    return MockLLM()


def build_embedder(s: Settings) -> Embedder:
    if s.embedding_mode == "openai":
        return OpenAIEmbedder(s.openai_api_key, s.openai_embedding_model, s.embedding_dim, s.openai_timeout_s)
    return HashEmbedder(s.embedding_dim)
