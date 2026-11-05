from __future__ import annotations

from typing import Protocol

from app.models import ReasoningOutput, ReasoningRequest


class LLMError(RuntimeError):
    """Provider unavailable / timeout / malformed output."""


class LLMProvider(Protocol):
    name: str

    def reason(self, req: ReasoningRequest) -> ReasoningOutput: ...
