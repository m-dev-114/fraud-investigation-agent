"""
Investigation workflow orchestration using LangGraph.

Pipeline:
  Transaction -> ML Risk Score -> AI Investigation (parallel-style sub-agents,
  executed sequentially for reliability) -> Evidence -> Risk Decision
  -> (Human Review happens via the API afterwards) -> Audit

Each node appends structured events so the full trace is persisted for the
Investigation timeline / Audit page. The graph is intentionally linear and
deterministic in control flow (per the brief: "prioritize a reliable working
workflow over complicated multi-agent architecture") — LangGraph is used for
clean orchestration and future extensibility, not to add nondeterminism.
"""
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from sqlalchemy.orm import Session
from app import models as m
from app.agents import sub_agents
from app.agents import llm_explainer
from app.ml import predict as ml_predict


class InvestigationState(TypedDict, total=False):
    db: Any
    txn: Any
    customer: Any
    customers_df: Any
    merchants_df: Any
    devices_df: Any
    ml_scores: Dict[str, Any]
    evidence: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    risk_score: float
    risk_level: str
    recommendation: str
    summary: str
    engine_used: str


def _log(state: InvestigationState, step: str, event_type: str, title: str, detail: dict):
    state.setdefault("events", []).append({
        "step": step, "event_type": event_type, "title": title, "detail": detail,
    })


def node_ml_score(state: InvestigationState) -> InvestigationState:
    txn = state["txn"]
    _log(state, "ml_risk_model", "tool_call", "Scoring transaction with ML models",
         {"transaction_id": txn.id})
    txn_row = {
        "id": txn.id, "customer_id": txn.customer_id, "merchant_id": txn.merchant_id,
        "device_id": txn.device_id, "amount": txn.amount, "channel": txn.channel,
        "status": txn.status, "txn_lat": txn.txn_lat, "txn_lon": txn.txn_lon,
        "txn_country": txn.txn_country, "ip_address": txn.ip_address,
        "created_at": txn.created_at,
    }
    scores = ml_predict.score_transaction(
        txn_row, state["customers_df"], state["merchants_df"], state["devices_df"]
    )
    state["ml_scores"] = scores
    _log(state, "ml_risk_model", "tool_result", "ML scores computed", {
        "xgboost_probability": scores.get("xgboost_probability"),
        "logreg_probability": scores.get("logreg_probability"),
    })
    return state


def node_transaction_agent(state: InvestigationState) -> InvestigationState:
    db, txn = state["db"], state["txn"]
    _log(state, "transaction_agent", "tool_call", "Analyzing transaction amount vs. customer baseline", {})
    history = db.query(m.Transaction).filter(m.Transaction.customer_id == txn.customer_id).all()
    ev = sub_agents.transaction_agent(db, txn, history)
    state.setdefault("evidence", []).extend(ev)
    _log(state, "transaction_agent", "tool_result", f"Found {len(ev)} evidence item(s)", {"count": len(ev)})
    return state


def node_velocity(state: InvestigationState) -> InvestigationState:
    db, txn = state["db"], state["txn"]
    _log(state, "velocity_agent", "tool_call", "Checking transaction velocity in trailing 1h window", {})
    ev = sub_agents.velocity_agent(db, txn)
    state.setdefault("evidence", []).extend(ev)
    _log(state, "velocity_agent", "tool_result", f"Found {len(ev)} evidence item(s)", {"count": len(ev)})
    return state


def node_device_agent(state: InvestigationState) -> InvestigationState:
    db, txn = state["db"], state["txn"]
    _log(state, "device_agent", "tool_call", "Checking device trust & fan-out across accounts", {})
    ev = sub_agents.device_agent(db, txn)
    state.setdefault("evidence", []).extend(ev)
    _log(state, "device_agent", "tool_result", f"Found {len(ev)} evidence item(s)", {"count": len(ev)})
    return state


def node_merchant_agent(state: InvestigationState) -> InvestigationState:
    db, txn = state["db"], state["txn"]
    _log(state, "merchant_agent", "tool_call", "Checking merchant risk rating", {})
    ev = sub_agents.merchant_agent(db, txn)
    state.setdefault("evidence", []).extend(ev)
    _log(state, "merchant_agent", "tool_result", f"Found {len(ev)} evidence item(s)", {"count": len(ev)})
    return state


def node_network_agent(state: InvestigationState) -> InvestigationState:
    db, txn, customer = state["db"], state["txn"], state["customer"]
    _log(state, "network_location_agent", "tool_call",
         "Checking geolocation, travel speed, and shared IP fan-out", {})
    ev = sub_agents.network_location_agent(db, txn, customer)
    state.setdefault("evidence", []).extend(ev)
    _log(state, "network_location_agent", "tool_result", f"Found {len(ev)} evidence item(s)", {"count": len(ev)})
    return state


def node_customer_agent(state: InvestigationState) -> InvestigationState:
    db, txn, customer = state["db"], state["txn"], state["customer"]
    _log(state, "customer_agent", "tool_call", "Checking account risk segment, KYC, and dispute history", {})
    ev = sub_agents.customer_agent(db, customer, txn)
    state.setdefault("evidence", []).extend(ev)
    _log(state, "customer_agent", "tool_result", f"Found {len(ev)} evidence item(s)", {"count": len(ev)})
    return state


def node_risk_decision(state: InvestigationState) -> InvestigationState:
    """Deterministic risk scoring: blends the ML probability with rule-evidence
    weight. The LLM (if used) never touches this number."""
    evidence = state.get("evidence", [])
    ml = state.get("ml_scores", {})
    xgb_p = ml.get("xgboost_probability")
    rule_weight = min(sum(e["weight"] for e in evidence), 70)

    if xgb_p is not None:
        ml_component = xgb_p * 100 * 0.6
        rule_component = rule_weight * 0.4
    else:
        ml_component = 0
        rule_component = rule_weight

    risk_score = round(min(ml_component + rule_component, 100), 1)

    if risk_score >= 75:
        risk_level, recommendation = "critical", "block"
    elif risk_score >= 45:
        risk_level, recommendation = "high", "escalate"
    elif risk_score >= 20:
        risk_level, recommendation = "medium", "escalate"
    else:
        risk_level, recommendation = "low", "approve"

    state["risk_score"] = risk_score
    state["risk_level"] = risk_level
    state["recommendation"] = recommendation
    _log(state, "risk_decision_engine", "decision",
         f"Computed risk score {risk_score}/100 ({risk_level}) -> recommend {recommendation}",
         {
             "risk_score": risk_score, "risk_level": risk_level, "recommendation": recommendation,
             "ml_component": round(ml_component, 1), "rule_component": round(rule_component, 1),
             "evidence_count": len(evidence),
         })
    return state


def node_summary(state: InvestigationState) -> InvestigationState:
    txn = state["txn"]
    engine_used = "deterministic"
    summary = None
    if state.get("ml_scores", {}) is not None:
        pass
    try:
        from app.config import settings
        if settings.LLM_API_KEY:
            _log(state, "llm_explainer", "tool_call", "Requesting LLM narrative explanation", {})
            summary = llm_explainer.generate_summary(
                transaction={
                    "id": txn.id, "amount": txn.amount, "channel": txn.channel,
                    "city": txn.txn_city, "country": txn.txn_country,
                    "created_at": str(txn.created_at),
                },
                ml_scores=state.get("ml_scores", {}),
                evidence=state.get("evidence", []),
                risk_score=state["risk_score"],
                risk_level=state["risk_level"],
            )
            engine_used = "llm"
    except Exception as exc:  # noqa: BLE001 - fall back gracefully, demo must still work
        _log(state, "llm_explainer", "tool_result", "LLM explanation failed, using deterministic summary",
             {"error": str(exc)})
        summary = None

    if not summary:
        summary = deterministic_summary(state)

    state["summary"] = summary
    state["engine_used"] = engine_used
    _log(state, "llm_explainer" if engine_used == "llm" else "summary_engine", "tool_result",
         "Investigation summary generated", {"engine_used": engine_used})
    return state


def deterministic_summary(state: InvestigationState) -> str:
    txn = state["txn"]
    evidence = sorted(state.get("evidence", []), key=lambda e: e["weight"], reverse=True)
    risk_level = state["risk_level"]
    ml = state.get("ml_scores", {})
    xgb_p = ml.get("xgboost_probability")

    if not evidence:
        base = (
            f"Transaction {txn.id} for ₹{txn.amount:,.2f} shows no significant risk indicators. "
            f"ML model fraud probability: {xgb_p:.1%} if xgb_p is not None else 'unavailable'." if xgb_p is not None
            else f"Transaction {txn.id} for ₹{txn.amount:,.2f} shows no significant risk indicators."
        )
        return f"Transaction {txn.id} for ₹{txn.amount:,.2f} shows no significant rule-based risk indicators, consistent with the customer's normal behavior. ML fraud probability: {f'{xgb_p:.1%}' if xgb_p is not None else 'unavailable'}. Overall risk level: {risk_level}."

    top = evidence[0]
    lines = [
        f"Transaction {txn.id} for ₹{txn.amount:,.2f} was assessed as {risk_level.upper()} risk "
        f"(score {state['risk_score']}/100)."
    ]
    if xgb_p is not None:
        lines.append(f"The XGBoost model assigned a fraud probability of {xgb_p:.1%}.")
    lines.append(f"The most significant finding is: {top['title']} — {top['description']}")
    if len(evidence) > 1:
        others = ", ".join(e["title"] for e in evidence[1:4])
        lines.append(f"Additional contributing evidence: {others}.")
    return " ".join(lines)


def build_graph():
    graph = StateGraph(InvestigationState)
    graph.add_node("ml_score", node_ml_score)
    graph.add_node("transaction_agent", node_transaction_agent)
    graph.add_node("velocity_agent", node_velocity)
    graph.add_node("device_agent", node_device_agent)
    graph.add_node("merchant_agent", node_merchant_agent)
    graph.add_node("network_agent", node_network_agent)
    graph.add_node("customer_agent", node_customer_agent)
    graph.add_node("risk_decision", node_risk_decision)
    graph.add_node("summarize_investigation", node_summary)

    graph.set_entry_point("ml_score")
    graph.add_edge("ml_score", "transaction_agent")
    graph.add_edge("transaction_agent", "velocity_agent")
    graph.add_edge("velocity_agent", "device_agent")
    graph.add_edge("device_agent", "merchant_agent")
    graph.add_edge("merchant_agent", "network_agent")
    graph.add_edge("network_agent", "customer_agent")
    graph.add_edge("customer_agent", "risk_decision")
    graph.add_edge("risk_decision", "summarize_investigation")
    graph.add_edge("summarize_investigation", END)
    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def run_investigation_pipeline(db: Session, txn: m.Transaction, customer: m.Customer,
                                customers_df, merchants_df, devices_df) -> InvestigationState:
    graph = get_graph()
    initial_state: InvestigationState = {
        "db": db, "txn": txn, "customer": customer,
        "customers_df": customers_df, "merchants_df": merchants_df, "devices_df": devices_df,
        "evidence": [], "events": [],
    }
    final_state = graph.invoke(initial_state)
    return final_state
