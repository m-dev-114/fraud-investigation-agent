"""
Trains a Logistic Regression baseline and an XGBoost model on the synthetic
transaction data, using a time-based train/test split (no leakage).

Saves:
  app/models_store/logreg.joblib
  app/models_store/xgboost.joblib
  app/models_store/scaler.joblib
  app/models_store/metrics.json
  app/models_store/feature_columns.json

Run:
  python scripts/train_model.py
"""
import os
import sys
import json
import datetime as dt
import numpy as np
import pandas as pd
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    precision_score, recall_score, f1_score, roc_auc_score,
    average_precision_score, confusion_matrix
)
from xgboost import XGBClassifier

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.ml.features import build_features, FEATURE_COLUMNS  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "models_store")
os.makedirs(MODEL_DIR, exist_ok=True)


def load_data():
    customers = pd.read_csv(os.path.join(DATA_DIR, "customers.csv"))
    merchants = pd.read_csv(os.path.join(DATA_DIR, "merchants.csv"))
    devices = pd.read_csv(os.path.join(DATA_DIR, "devices.csv"))
    transactions = pd.read_csv(os.path.join(DATA_DIR, "transactions.csv"))
    transactions["created_at"] = pd.to_datetime(transactions["created_at"])
    return customers, merchants, devices, transactions


def evaluate(model_name, y_true, y_pred_proba, threshold=0.5):
    y_pred = (y_pred_proba >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    return {
        "model_name": model_name,
        "trained_at": dt.datetime.utcnow().isoformat(),
        "n_train": None,  # filled by caller
        "n_test": int(len(y_true)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_pred_proba)),
        "pr_auc": float(average_precision_score(y_true, y_pred_proba)),
        "confusion_matrix": {
            "true_negative": int(tn), "false_positive": int(fp),
            "false_negative": int(fn), "true_positive": int(tp),
        },
    }


def main():
    print("Loading data...")
    customers, merchants, devices, transactions = load_data()

    print(f"Building features for {len(transactions)} transactions...")
    feat = build_features(transactions, customers, merchants, devices)
    df = transactions[["id", "created_at", "fraud_label"]].merge(feat, on="id")
    df = df.sort_values("created_at").reset_index(drop=True)

    # Time-based split: first 80% chronologically -> train, last 20% -> test.
    # This avoids leakage and mirrors a real production rollout.
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]

    X_train, y_train = train_df[FEATURE_COLUMNS], train_df["fraud_label"]
    X_test, y_test = test_df[FEATURE_COLUMNS], test_df["fraud_label"]
    print(f"Train: {len(X_train)} ({y_train.mean():.4f} fraud rate)  "
          f"Test: {len(X_test)} ({y_test.mean():.4f} fraud rate)")

    # --- Logistic Regression baseline ---------------------------------------
    print("Training Logistic Regression baseline...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    logreg = LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0)
    logreg.fit(X_train_scaled, y_train)
    logreg_proba = logreg.predict_proba(X_test_scaled)[:, 1]
    logreg_metrics = evaluate("logistic_regression", y_test, logreg_proba)
    logreg_metrics["n_train"] = int(len(X_train))
    logreg_metrics["feature_importance"] = sorted(
        [{"feature": f, "importance": float(c)} for f, c in zip(FEATURE_COLUMNS, logreg.coef_[0])],
        key=lambda x: abs(x["importance"]), reverse=True
    )[:15]
    print(f"  LogReg  -> P:{logreg_metrics['precision']:.3f} R:{logreg_metrics['recall']:.3f} "
          f"F1:{logreg_metrics['f1']:.3f} ROC-AUC:{logreg_metrics['roc_auc']:.3f} "
          f"PR-AUC:{logreg_metrics['pr_auc']:.3f}")

    # --- XGBoost main model ---------------------------------------------------
    print("Training XGBoost...")
    scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
    xgb = XGBClassifier(
        n_estimators=300, max_depth=5, learning_rate=0.08,
        subsample=0.85, colsample_bytree=0.85,
        scale_pos_weight=scale_pos_weight, eval_metric="aucpr",
        random_state=42, n_jobs=-1,
    )
    xgb.fit(X_train, y_train)
    xgb_proba = xgb.predict_proba(X_test)[:, 1]
    xgb_metrics = evaluate("xgboost", y_test, xgb_proba)
    xgb_metrics["n_train"] = int(len(X_train))
    importances = xgb.feature_importances_
    xgb_metrics["feature_importance"] = sorted(
        [{"feature": f, "importance": float(i)} for f, i in zip(FEATURE_COLUMNS, importances)],
        key=lambda x: x["importance"], reverse=True
    )[:15]
    print(f"  XGBoost -> P:{xgb_metrics['precision']:.3f} R:{xgb_metrics['recall']:.3f} "
          f"F1:{xgb_metrics['f1']:.3f} ROC-AUC:{xgb_metrics['roc_auc']:.3f} "
          f"PR-AUC:{xgb_metrics['pr_auc']:.3f}")

    # --- Save artifacts ---------------------------------------------------------
    joblib.dump(logreg, os.path.join(MODEL_DIR, "logreg.joblib"))
    joblib.dump(scaler, os.path.join(MODEL_DIR, "scaler.joblib"))
    joblib.dump(xgb, os.path.join(MODEL_DIR, "xgboost.joblib"))
    with open(os.path.join(MODEL_DIR, "feature_columns.json"), "w") as f:
        json.dump(FEATURE_COLUMNS, f, indent=2)
    with open(os.path.join(MODEL_DIR, "metrics.json"), "w") as f:
        json.dump({"logistic_regression": logreg_metrics, "xgboost": xgb_metrics}, f, indent=2)

    print(f"\nSaved model artifacts to {MODEL_DIR}")


if __name__ == "__main__":
    main()
