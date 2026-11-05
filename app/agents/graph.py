"""LangGraph definition (V04): load -> retrieve -> reason <-> tools -> diagnose -> persist. `max_steps` bounds the loop."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.nodes import make_nodes
from app.agents.state import AgentState, RunDeps


def build_graph(deps: RunDeps):
    n = make_nodes(deps)
    g = StateGraph(AgentState)
    for name in ("load_incident", "retrieve", "reason", "tools", "diagnose", "persist"):
        g.add_node(name, n[name])
    g.set_entry_point("load_incident")
    g.add_edge("load_incident", "retrieve")
    g.add_edge("retrieve", "reason")
    g.add_conditional_edges("reason", n["route_after_reason"], {"tools": "tools", "diagnose": "diagnose"})
    g.add_edge("tools", "reason")
    g.add_edge("diagnose", "persist")
    g.add_edge("persist", END)
    return g.compile()
