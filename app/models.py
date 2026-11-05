"""Typed domain contracts shared by every layer (API, agent, gateways, stores)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["technician", "supervisor", "administrator"]
Status = Literal["completed", "needs_more_data", "pending_approval", "max_steps_reached", "rejected"]


class Principal(BaseModel):
    """Authenticated caller. Built ONLY from a verified JWT, never from the request body."""

    model_config = ConfigDict(frozen=True)
    user_id: str
    role: str
    plants: tuple[str, ...] = ()

    def can_see_plant(self, plant_id: str) -> bool:
        return "*" in self.plants or plant_id in self.plants


class DiagnoseRequest(BaseModel):
    incident_id: str = Field(pattern=r"^INC-[A-Za-z0-9-]{1,32}$")
    equipment_id: str = Field(min_length=1, max_length=32)
    plant_id: str = Field(min_length=1, max_length=32)
    symptoms: list[str] = Field(default_factory=list, max_length=20)
    message: str = Field(default="", max_length=2000)  # UNTRUSTED free text


class Citation(BaseModel):
    source_id: str
    source_type: str
    snippet: str


class Observation(BaseModel):
    name: str
    value: float | str
    unit: str = ""
    source: str
    equipment_id: str


class Hypothesis(BaseModel):
    cause: str
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)
    rationale: str = ""


class ProposedAction(BaseModel):
    action_id: str | None = None
    action_type: str
    summary: str
    params: dict[str, Any] = Field(default_factory=dict)
    decision: Literal["proposed", "allowed", "pending_approval", "denied"] = "proposed"
    reason: str = ""
    approval_id: str | None = None


class DiagnosisResponse(BaseModel):
    incident_id: str
    run_id: str
    status: Status
    observations: list[Observation] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    recommended_checks: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    trace_id: str
    resumed: bool = False
    prior_run_count: int = 0
    steps: int = 0
    node_timings_ms: dict[str, float] = Field(default_factory=dict)


class Chunk(BaseModel):
    chunk_id: str
    source_id: str
    source_type: Literal["failure", "manual", "procedure"]
    plant_id: str | None = None  # None = global document (manuals/procedures)
    equipment_id: str | None = None
    equipment_type: str = "all"
    root_cause: str | None = None
    symptoms: list[str] = Field(default_factory=list)
    text: str
    score: float = 0.0


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ReasoningRequest(BaseModel):
    equipment_id: str
    plant_id: str
    symptoms: list[str]
    user_message: str  # untrusted
    evidence: list[Chunk]  # untrusted
    observations: list[Observation]
    tool_errors: list[str] = Field(default_factory=list)
    prior_hypotheses: list[Hypothesis] = Field(default_factory=list)
    step: int = 0


class ReasoningOutput(BaseModel):
    tool_calls: list[ToolCall] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    recommended_checks: list[str] = Field(default_factory=list)
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    needs_more_data: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
