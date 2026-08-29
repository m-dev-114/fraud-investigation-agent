import datetime as dt
from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models as m


def get_summary(db: Session):
    total = db.query(func.count(m.Transaction.id)).scalar() or 0
    flagged = db.query(func.count(m.Transaction.id)).filter(m.Transaction.risk_score >= 20).scalar() or 0
    critical = db.query(func.count(m.Transaction.id)).filter(m.Transaction.risk_score >= 75).scalar() or 0
    fraud_count = db.query(func.count(m.Transaction.id)).filter(m.Transaction.fraud_label == 1).scalar() or 0
    fraud_rate = (fraud_count / total) if total else 0.0

    total_amount = db.query(func.coalesce(func.sum(m.Transaction.amount), 0.0)).scalar() or 0.0
    amount_at_risk = db.query(func.coalesce(func.sum(m.Transaction.amount), 0.0)).filter(
        m.Transaction.risk_score >= 45
    ).scalar() or 0.0

    since = dt.datetime.utcnow() - dt.timedelta(days=30)
    by_day_rows = (
        db.query(func.date(m.Transaction.created_at).label("day"),
                  func.count(m.Transaction.id).label("count"),
                  func.sum(m.Transaction.fraud_label).label("fraud_count"))
        .filter(m.Transaction.created_at >= since)
        .group_by(func.date(m.Transaction.created_at))
        .order_by(func.date(m.Transaction.created_at))
        .all()
    )
    transactions_by_day = [
        {"date": str(r.day), "count": int(r.count), "fraud_count": int(r.fraud_count or 0)}
        for r in by_day_rows
    ]

    fraud_type_rows = (
        db.query(m.Transaction.fraud_type, func.count(m.Transaction.id))
        .filter(m.Transaction.fraud_label == 1)
        .group_by(m.Transaction.fraud_type)
        .all()
    )
    fraud_by_type = [{"type": t, "count": c} for t, c in fraud_type_rows]

    risk_dist_rows = []
    buckets = [("low", 0, 20), ("medium", 20, 45), ("high", 45, 75), ("critical", 75, 101)]
    for label, lo, hi in buckets:
        cnt = db.query(func.count(m.Transaction.id)).filter(
            m.Transaction.risk_score >= lo, m.Transaction.risk_score < hi
        ).scalar() or 0
        risk_dist_rows.append({"level": label, "count": cnt})

    recent_inv = (
        db.query(m.Investigation)
        .filter(m.Investigation.status == "completed")
        .order_by(m.Investigation.completed_at.desc())
        .limit(10)
        .all()
    )
    recent_investigations = [
        {
            "id": inv.id, "transaction_id": inv.transaction_id, "risk_level": inv.risk_level,
            "risk_score": inv.risk_score, "recommendation": inv.recommendation,
            "completed_at": str(inv.completed_at),
        }
        for inv in recent_inv
    ]

    return {
        "total_transactions": total,
        "flagged_transactions": flagged,
        "critical_transactions": critical,
        "fraud_rate": round(fraud_rate, 4),
        "amount_at_risk": round(amount_at_risk, 2),
        "total_amount": round(total_amount, 2),
        "transactions_by_day": transactions_by_day,
        "fraud_by_type": fraud_by_type,
        "risk_distribution": risk_dist_rows,
        "recent_investigations": recent_investigations,
    }
