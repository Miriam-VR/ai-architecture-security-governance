"""Composition root: wires adapters and gateways. Tests override any piece via keyword arguments."""

from __future__ import annotations

from dataclasses import dataclass

from app.actions.cmms import MockCMMS
from app.actions.executor import ActionExecutor
from app.actions.gateway import ActionGateway
from app.actions.queue import ActionQueue, InlineQueue, SqsQueue
from app.config import Settings
from app.governance.approvals import ApprovalService
from app.governance.audit import AuditLog
from app.governance.policies import PolicyEngine
from app.llm.base import LLMProvider
from app.llm.embeddings import Embedder
from app.llm.factory import build_embedder, build_llm
from app.mcp.client import MCPClient
from app.mcp.server import MaintenanceMCPServer
from app.mcp.tool_gateway import ToolGateway
from app.memory.gateway import MemoryGateway
from app.retrieval.retriever import Retriever
from app.store.base import Store
from app.store.factory import build_store


@dataclass
class Container:
    settings: Settings
    store: Store
    llm: LLMProvider
    embedder: Embedder
    audit: AuditLog
    policy: PolicyEngine
    retriever: Retriever
    tools: ToolGateway
    memory: MemoryGateway
    actions: ActionGateway
    approvals: ApprovalService
    executor: ActionExecutor
    queue: ActionQueue
    cmms: MockCMMS


def build_container(settings: Settings, *, store: Store | None = None, llm: LLMProvider | None = None, embedder: Embedder | None = None,
                    queue: ActionQueue | None = None, cmms: MockCMMS | None = None) -> Container:
    auto_ingest = store is None and settings.store_mode == "memory"
    store = store or build_store(settings)
    llm = llm or build_llm(settings)
    embedder = embedder or build_embedder(settings)
    if auto_ingest:  # memory mode has no separate `scripts/ingest.py` step: index the synthetic corpus at start-up
        from app.retrieval.ingest import ingest

        ingest(store, embedder)
    audit = AuditLog(store)
    policy = PolicyEngine(store, audit)
    cmms = cmms or MockCMMS()
    executor = ActionExecutor(store, policy, audit, cmms)
    if queue is None:
        if settings.action_queue_mode == "sqs":
            queue = SqsQueue(settings.action_queue_url, settings.aws_region)
        else:
            queue = InlineQueue()
    if isinstance(queue, InlineQueue) and queue.handler is None:
        queue.handler = executor.handle_message
    approvals = ApprovalService(store, audit, queue, settings.approval_ttl_minutes)
    server = MaintenanceMCPServer(store, settings.mcp_shared_secret or "dev-only-mcp-secret")
    client = MCPClient(server.handle, settings.mcp_shared_secret or "dev-only-mcp-secret")
    return Container(
        settings=settings, store=store, llm=llm, embedder=embedder, audit=audit, policy=policy,
        retriever=Retriever(store, embedder, settings.rag_top_k, settings.rag_min_score),
        tools=ToolGateway(client, store, audit), memory=MemoryGateway(store, audit),
        actions=ActionGateway(store, policy, approvals, queue, audit), approvals=approvals, executor=executor, queue=queue, cmms=cmms)
