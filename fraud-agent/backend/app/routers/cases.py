import datetime as dt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models as m
from app.schemas import DecisionRequest, DecisionOut

router = APIRouter(prefix="/api/cases", tags=["cases"])

VALID_DECISIONS = {"approve", "block", "escalate"}


@router.post("/{case_id}/decision", response_model=DecisionOut)
def decide_case(case_id: str, body: DecisionRequest, db: Session = Depends(get_db)):
    if body.decision not in VALID_DECISIONS:
        raise HTTPException(400, f"decision must be one of {VALID_DECISIONS}")

    case = db.query(m.Case).filter(m.Case.id == case_id).first()
    if not case:
        raise HTTPException(404, "Case not found")

    investigation = (
        db.query(m.Investigation)
        .filter(m.Investigation.case_id == case_id)
        .order_by(m.Investigation.completed_at.desc())
        .first()
    )

    decision = m.AnalystDecision(
        case_id=case_id, investigation_id=investigation.id if investigation else None,
        analyst_name=body.analyst_name, decision=body.decision, notes=body.notes,
    )
    db.add(decision)

    case.status = "closed"
    case.closed_at = dt.datetime.utcnow()

    txn = db.query(m.Transaction).filter(m.Transaction.id == case.transaction_id).first()

    db.add(m.AuditLog(
        case_id=case_id, transaction_id=case.transaction_id, actor=f"analyst:{body.analyst_name}",
        action=f"decision_{body.decision}",
        detail={"notes": body.notes, "investigation_id": investigation.id if investigation else None},
    ))

    db.commit()
    db.refresh(decision)
    return decision
