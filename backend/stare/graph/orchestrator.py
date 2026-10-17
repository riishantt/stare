"""LangGraph orchestrator: shared ResearchState, checkpoint after every step, two hard approval gates.

    intake -> plan_gate* -> research -> precedent -> opposing_counsel -> firewall
           -> (too few verified and loops left ? research : memo) -> memo_firewall -> memo_gate*
           -> (changes requested ? memo : END)
    * = LangGraph interrupt: the graph cannot continue until an approval is recorded (Section 5.3.4).
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from stare.agents.base import AgentDeps
from stare.agents.firewall_agent import FirewallAgent
from stare.agents.intake import IntakeAgent
from stare.agents.memo import MemoAgent
from stare.agents.memo_firewall import MemoFirewallAgent
from stare.agents.opposing import OpposingCounselAgent
from stare.agents.precedent import PrecedentAgent
from stare.agents.research import ResearchAgent
from stare.agents.state import ResearchState


def plan_gate(state: ResearchState) -> dict[str, Any]:
    decision = interrupt({"type": "plan_approval", "plan": state.get("plan")})
    if decision.get("action") == "cancel":
        return {"status": "cancelled"}
    return {
        "plan": decision["plan"],
        "plan_approved": True,
        "plan_approved_at_ms": decision.get("at_ms") or int(time.time() * 1000),
        "status": "researching",
        "loop_count": 0,
        "rejected": [],
    }


def memo_gate(state: ResearchState) -> dict[str, Any]:
    decision = interrupt({"type": "memo_approval"})
    action = decision.get("action")
    if action == "changes":
        return {"memo_feedback": decision.get("instruction", ""), "status": "researching"}
    if action == "cancel":
        return {"status": "cancelled"}
    update: dict[str, Any] = {"memo_approved": True, "approved_by": decision.get("user_id"), "status": "approved"}
    if decision.get("memo"):
        update["memo"] = decision["memo"]  # attorney edits, already re-verified by the service
    return update


def after_plan(state: ResearchState) -> str:
    return END if state.get("status") == "cancelled" else "research"


def after_firewall(state: ResearchState) -> str:
    return "research" if state.get("retry_research") else "memo"


def after_memo_gate(state: ResearchState) -> str:
    return "memo" if state.get("memo_feedback") and state.get("status") != "cancelled" else END


def build_graph(deps: AgentDeps, checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(ResearchState)
    g.add_node("intake", IntakeAgent(deps).run)
    g.add_node("plan_gate", plan_gate)
    g.add_node("research", ResearchAgent(deps).run)
    g.add_node("precedent", PrecedentAgent(deps).run)
    g.add_node("opposing_counsel", OpposingCounselAgent(deps).run)
    g.add_node("firewall", FirewallAgent(deps).run)
    g.add_node("memo", MemoAgent(deps).run)
    g.add_node("memo_firewall", MemoFirewallAgent(deps).run)
    g.add_node("memo_gate", memo_gate)

    g.add_edge(START, "intake")
    g.add_edge("intake", "plan_gate")
    g.add_conditional_edges("plan_gate", after_plan, ["research", END])
    g.add_edge("research", "precedent")
    g.add_edge("precedent", "opposing_counsel")
    g.add_edge("opposing_counsel", "firewall")
    g.add_conditional_edges("firewall", after_firewall, ["research", "memo"])
    g.add_edge("memo", "memo_firewall")
    g.add_edge("memo_firewall", "memo_gate")
    g.add_conditional_edges("memo_gate", after_memo_gate, ["memo", END])
    return g.compile(checkpointer=checkpointer or make_checkpointer(deps))


def make_checkpointer(deps: AgentDeps) -> BaseCheckpointSaver:
    if deps.settings.is_postgres:
        from langgraph.checkpoint.postgres import PostgresSaver  # optional dependency
        from psycopg import Connection

        conn = Connection.connect(deps.settings.db_url.replace("+psycopg", ""), autocommit=True)
        saver = PostgresSaver(conn)
        saver.setup()
        return saver
    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(str(deps.settings.checkpoint_path), check_same_thread=False)
    return SqliteSaver(conn)
