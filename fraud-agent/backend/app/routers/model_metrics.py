from fastapi import APIRouter
from app.ml import predict as ml_predict
from app.schemas import ModelMetricsResponse

router = APIRouter(prefix="/api/model", tags=["model"])


@router.get("/metrics", response_model=ModelMetricsResponse)
def get_metrics():
    if not ml_predict.is_loaded():
        ml_predict.load_models()
    metrics = ml_predict.get_metrics()
    return ModelMetricsResponse(
        logistic_regression=metrics.get("logistic_regression"),
        xgboost=metrics.get("xgboost"),
    )
