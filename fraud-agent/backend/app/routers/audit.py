from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models as m
from app.schemas import AuditLogOut

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/{case_id}", response_model=list[AuditLogOut])
def get_audit_trail(case_id: str, db: Session = Depends(get_db)):
    logs = (
        db.query(m.AuditLog)
        .filter(m.AuditLog.case_id == case_id)
        .order_by(m.AuditLog.created_at.asc())
        .all()
    )
    return logs
