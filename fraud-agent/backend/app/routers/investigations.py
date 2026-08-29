from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models as m
from app.schemas import RunInvestigationRequest, InvestigationOut, InvestigationEventOut
from app.services import investigation_service

router = APIRouter(prefix="/api", tags=["investigations"])


@router.post("/investigations/{transaction_id}/run", response_model=InvestigationOut)
def run_investigation(transaction_id: str, body: RunInvestigationRequest = RunInvestigationRequest(),
                       db: Session = Depends(get_db)):
    try:
        inv = investigation_service.run_investigation(db, transaction_id, force_rerun=body.force_rerun)
    except ValueError as e:
        raise HTTPException(404, str(e))
    evidence = db.query(m.Evidence).filter(m.Evidence.investigation_id == inv.id).all()
    out = InvestigationOut.model_validate(inv)
    out.evidence = evidence
    return out


@router.get("/investigations/{investigation_id}", response_model=InvestigationOut)
def get_investigation(investigation_id: str, db: Session = Depends(get_db)):
    inv = db.query(m.Investigation).filter(m.Investigation.id == investigation_id).first()
    if not inv:
        raise HTTPException(404, "Investigation not found")
    evidence = db.query(m.Evidence).filter(m.Evidence.investigation_id == inv.id).all()
    out = InvestigationOut.model_validate(inv)
    out.evidence = evidence
    return out


@router.get("/investigations/{investigation_id}/events", response_model=list[InvestigationEventOut])
def get_investigation_events(investigation_id: str, db: Session = Depends(get_db)):
    events = (
        db.query(m.InvestigationEvent)
        .filter(m.InvestigationEvent.investigation_id == investigation_id)
        .order_by(m.InvestigationEvent.created_at.asc())
        .all()
    )
    return events
