from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

from app.actions.gateway import ActionGateway
from app.llm.base import LLMProvider
from app.mcp.tool_gateway import ToolGateway
from app.memory.gateway import MemoryGateway
from app.models import DiagnoseRequest, Principal
from app.observability.telemetry import Timings
from app.retrieval.retriever import Retriever


class AgentState(TypedDict, total=False):
    incident: dict[str, Any]
    resumed: bool
    prior_run_count: int
    prior_hypotheses: list[dict[str, Any]]
    run_id: str
    step: int
    evidence: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    pending_tool_calls: list[dict[str, Any]]
    tool_errors: list[str]
    hypotheses: list[dict[str, Any]]
    recommended_checks: list[str]
    proposed_actions: list[dict[str, Any]]
    needs_more_data: bool
    status: str


@dataclass
class RunDeps:
    """Per-request dependencies. A new instance (and graph) per request => no shared mutable state."""

    principal: Principal
    request: DiagnoseRequest
    trace_id: str
    max_steps: int
    llm: LLMProvider
    retriever: Retriever
    tools: ToolGateway
    memory: MemoryGateway
    actions: ActionGateway
    timings: Timings = field(default_factory=Timings)
    tokens_in: int = 0
    tokens_out: int = 0
