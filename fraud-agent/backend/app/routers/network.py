from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import NetworkGraph
from app.services import network_service

router = APIRouter(prefix="/api/network", tags=["network"])


@router.get("/{transaction_id}", response_model=NetworkGraph)
def get_network(transaction_id: str, db: Session = Depends(get_db)):
    try:
        graph = network_service.build_network(db, transaction_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return graph
