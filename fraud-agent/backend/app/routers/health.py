from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.config import settings
from app.ml import predict as ml_predict
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    db_connected = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_connected = False

    if not ml_predict.is_loaded():
        ml_predict.load_models()

    return HealthResponse(
        status="ok" if db_connected else "degraded",
        env=settings.ENV,
        db_connected=db_connected,
        model_loaded=ml_predict.is_loaded(),
    )
