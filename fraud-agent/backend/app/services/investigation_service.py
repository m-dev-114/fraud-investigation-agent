import datetime as dt
from sqlalchemy.orm import Session
from app import models as m
from app.agents.orchestrator import run_investigation_pipeline
from app.services.reference_data import get_reference_frames


def run_investigation(db: Session, transaction_id: str, force_rerun: bool = False) -> m.Investigation:
    txn = db.query(m.Transaction).filter(m.Transaction.id == transaction_id).first()
    if txn is None:
        raise ValueError(f"Transaction {transaction_id} not found")

    if not force_rerun:
        existing = (
            db.query(m.Investigation)
            .filter(m.Investigation.transaction_id == transaction_id, m.Investigation.status == "completed")
            .order_by(m.Investigation.completed_at.desc())
            .first()
        )
        if existing:
            return existing

    customer = db.query(m.Customer).filter(m.Customer.id == txn.customer_id).first()

    investigation = m.Investigation(
        transaction_id=transaction_id, status="running", started_at=dt.datetime.utcnow(),
    )
    db.add(investigation)
    db.commit()
    db.refresh(investigation)

    txn.investigation_status = "in_progress"
    db.commit()

    _audit(db, None, transaction_id, "system", "investigation_started",
           {"investigation_id": investigation.id})

    try:
        customers_df, merchants_df, devices_df = get_reference_frames(db)
        final_state = run_investigation_pipeline(db, txn, customer, customers_df, merchants_df, devices_df)
    except Exception as exc:  # noqa: BLE001
        investigation.status = "failed"
        investigation.summary = f"Investigation failed: {exc}"
        investigation.completed_at = dt.datetime.utcnow()
        db.commit()
        _audit(db, None, transaction_id, "system", "investigation_failed", {"error": str(exc)})
        raise

    # Persist events
    for i, ev in enumerate(final_state.get("events", [])):
        db.add(m.InvestigationEvent(
            investigation_id=investigation.id, step=ev["step"], event_type=ev["event_type"],
            title=ev["title"], detail=ev.get("detail", {}),
            created_at=investigation.started_at + dt.timedelta(seconds=i),
        ))

    # Persist evidence
    for ev in final_state.get("evidence", []):
        db.add(m.Evidence(
            investigation_id=investigation.id, category=ev["category"], title=ev["title"],
            description=ev["description"], severity=ev["severity"], weight=ev["weight"],
            raw_data=ev.get("raw_data", {}),
        ))

    # Persist ML model predictions
    ml_scores = final_state.get("ml_scores", {})
    if ml_scores.get("xgboost_probability") is not None:
        db.add(m.ModelPrediction(
            transaction_id=transaction_id, model_name="xgboost", model_version="1.0",
            fraud_probability=ml_scores["xgboost_probability"],
            predicted_label=1 if ml_scores["xgboost_probability"] >= 0.5 else 0,
            feature_snapshot=ml_scores.get("features", {}),
        ))
        db.add(m.ModelPrediction(
            transaction_id=transaction_id, model_name="logistic_regression", model_version="1.0",
            fraud_probability=ml_scores["logreg_probability"],
            predicted_label=1 if ml_scores["logreg_probability"] >= 0.5 else 0,
            feature_snapshot={},
        ))

    investigation.status = "completed"
    investigation.risk_score = final_state.get("risk_score")
    investigation.fraud_probability = ml_scores.get("xgboost_probability")
    investigation.risk_level = final_state.get("risk_level")
    investigation.recommendation = final_state.get("recommendation")
    investigation.summary = final_state.get("summary")
    investigation.engine_used = final_state.get("engine_used", "deterministic")
    investigation.completed_at = dt.datetime.utcnow()

    txn.risk_score = investigation.risk_score
    txn.fraud_probability = investigation.fraud_probability
    txn.investigation_status = "completed"

    # Create a case for anything not a clear "approve"
    case = None
    if investigation.recommendation in ("block", "escalate"):
        case = m.Case(
            transaction_id=transaction_id, customer_id=txn.customer_id,
            status="open",
            priority="critical" if investigation.risk_level == "critical" else
                      "high" if investigation.risk_level == "high" else "medium",
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        investigation.case_id = case.id

    db.commit()
    db.refresh(investigation)

    _audit(db, case.id if case else None, transaction_id, "agent:risk_decision_engine",
           "investigation_completed",
           {"risk_score": investigation.risk_score, "risk_level": investigation.risk_level,
            "recommendation": investigation.recommendation, "engine_used": investigation.engine_used})

    return investigation


def _audit(db: Session, case_id, transaction_id, actor, action, detail):
    db.add(m.AuditLog(case_id=case_id, transaction_id=transaction_id, actor=actor,
                       action=action, detail=detail))
    db.commit()
