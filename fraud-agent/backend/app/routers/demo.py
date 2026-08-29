from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models as m

router = APIRouter(prefix="/api/demo", tags=["demo"])

DEMO_SPEC = [
    ("account_takeover", "Account Takeover", 1),
    ("fraud_ring", "Fraud Ring", 1),
    ("velocity_attack", "Velocity Attack", 1),
    ("impossible_travel", "Impossible Travel", 1),
    ("none", "Legitimate Transaction", 0),
]


@router.get("/cases")
def get_demo_cases(db: Session = Depends(get_db)):
    cases = []
    for fraud_type, label, fraud_label in DEMO_SPEC:
        q = db.query(m.Transaction).filter(
            m.Transaction.fraud_type == fraud_type, m.Transaction.fraud_label == fraud_label
        )
        if fraud_type == "none":
            # Pick a modest, device-linked, domestic transaction so it reliably
            # scores as low risk in the demo (a very large legit txn can still
            # look unusual relative to that customer's own history).
            q = q.filter(
                m.Transaction.amount.between(800, 3000),
                m.Transaction.device_id.isnot(None),
                m.Transaction.txn_country == "IN",
            )
            txn = q.order_by(m.Transaction.id.asc()).first()
        else:
            txn = q.order_by(m.Transaction.amount.desc()).first()
        if txn:
            cases.append({
                "label": label, "fraud_type": fraud_type, "transaction_id": txn.id,
                "amount": txn.amount, "customer_id": txn.customer_id,
            })
    return {"cases": cases}
