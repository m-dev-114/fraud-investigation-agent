import os
import json
import joblib
import pandas as pd
from app.config import settings
from app.ml.features import build_features, FEATURE_COLUMNS

_logreg = None
_xgb = None
_scaler = None
_metrics = None
_loaded = False


def _model_dir():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "models_store")


def load_models():
    global _logreg, _xgb, _scaler, _metrics, _loaded
    d = _model_dir()
    try:
        _logreg = joblib.load(os.path.join(d, "logreg.joblib"))
        _xgb = joblib.load(os.path.join(d, "xgboost.joblib"))
        _scaler = joblib.load(os.path.join(d, "scaler.joblib"))
        with open(os.path.join(d, "metrics.json")) as f:
            _metrics = json.load(f)
        _loaded = True
    except FileNotFoundError:
        _loaded = False
    return _loaded


def is_loaded():
    return _loaded


def get_metrics():
    return _metrics or {}


def score_transaction(txn_row: dict, customers_df, merchants_df, devices_df) -> dict:
    """
    txn_row: dict-like single transaction (must include fields used by build_features)
    customers_df/merchants_df/devices_df: pandas DataFrames of full reference tables
    Returns dict with xgboost + logreg probabilities and the feature snapshot.
    """
    if not _loaded:
        load_models()
    if not _loaded:
        return {"xgboost_probability": None, "logreg_probability": None, "features": {}}

    txn_df = pd.DataFrame([txn_row])
    feat = build_features(txn_df, customers_df, merchants_df, devices_df)
    X = feat[FEATURE_COLUMNS]

    xgb_proba = float(_xgb.predict_proba(X)[:, 1][0])
    X_scaled = _scaler.transform(X)
    logreg_proba = float(_logreg.predict_proba(X_scaled)[:, 1][0])

    return {
        "xgboost_probability": xgb_proba,
        "logreg_probability": logreg_proba,
        "features": X.iloc[0].to_dict(),
    }
