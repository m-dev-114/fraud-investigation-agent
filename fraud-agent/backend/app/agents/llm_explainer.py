"""
Optional LLM layer. If LLM_API_KEY is set, this asks Claude to write a
plain-English investigator summary of the evidence that has ALREADY been
collected and weighted by the deterministic rule agents + ML model.

The LLM never sees payment execution tools and cannot change the risk score
or the recommendation — it only narrates. If the call fails or no key is
configured, the caller falls back to a deterministic template summary
(see investigation_service.deterministic_summary) so the demo always works.
"""
import json
from app.config import settings

SYSTEM_PROMPT = """You are a fraud investigation analyst assistant at a fintech company.
You will be given: a transaction, ML risk scores, and a list of evidence items
already collected by rule-based investigation agents (amounts, weights and
severities are fixed and NOT yours to change).

Write a concise (3-5 sentence) investigator-style summary explaining WHY this
transaction is risky or not, referencing the concrete evidence given. Do not
invent evidence that isn't in the list. Do not state a final approve/block
decision — that is made by the deterministic risk engine, not you. End by
noting which single piece of evidence is most significant, if any."""


def generate_summary(transaction: dict, ml_scores: dict, evidence: list, risk_score: float, risk_level: str) -> str:
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY not configured")

    import anthropic
    client = anthropic.Anthropic(api_key=settings.LLM_API_KEY)

    user_payload = {
        "transaction": transaction,
        "ml_risk_scores": ml_scores,
        "computed_risk_score_0_100": risk_score,
        "computed_risk_level": risk_level,
        "evidence": evidence,
    }

    resp = client.messages.create(
        model=settings.LLM_MODEL,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(user_payload, default=str)}],
    )
    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts).strip()
