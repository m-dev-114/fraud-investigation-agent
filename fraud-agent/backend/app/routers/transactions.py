from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app import models as m
from app.schemas import TransactionListResponse, TransactionDetail

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    search: Optional[str] = None,
    status: Optional[str] = None,
    min_risk: Optional[float] = None,
    max_risk: Optional[float] = None,
    fraud_type: Optional[str] = None,
    investigation_status: Optional[str] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
):
    q = db.query(m.Transaction)

    if search:
        like = f"%{search}%"
        q = q.filter(or_(
            m.Transaction.id.ilike(like),
            m.Transaction.customer_id.ilike(like),
            m.Transaction.merchant_id.ilike(like),
            m.Transaction.txn_city.ilike(like),
        ))
    if status:
        q = q.filter(m.Transaction.status == status)
    if fraud_type:
        q = q.filter(m.Transaction.fraud_type == fraud_type)
    if investigation_status:
        q = q.filter(m.Transaction.investigation_status == investigation_status)
    if min_risk is not None:
        q = q.filter(m.Transaction.risk_score >= min_risk)
    if max_risk is not None:
        q = q.filter(m.Transaction.risk_score <= max_risk)

    total = q.count()

    sort_col = getattr(m.Transaction, sort_by, m.Transaction.created_at)
    q = q.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    items = q.offset((page - 1) * page_size).limit(page_size).all()

    return TransactionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{transaction_id}", response_model=TransactionDetail)
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    txn = db.query(m.Transaction).filter(m.Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    customer = db.query(m.Customer).filter(m.Customer.id == txn.customer_id).first()
    merchant = db.query(m.Merchant).filter(m.Merchant.id == txn.merchant_id).first()

    data = TransactionDetail.model_validate(txn)
    data.customer_name = customer.full_name if customer else None
    data.merchant_name = merchant.name if merchant else None
    return data
