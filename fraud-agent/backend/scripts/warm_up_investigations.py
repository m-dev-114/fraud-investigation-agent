"""
Pre-runs investigations on the 5 guaranteed demo cases plus a random sample
of other transactions, so the Dashboard (Flagged/Critical/Amount at Risk/
Recent Investigations) isn't empty the first time a judge opens the app.

Run this AFTER seed_database.py, pointed at the same DATABASE_URL:

  python scripts/warm_up_investigations.py
"""
import os
import sys
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.database import SessionLocal  # noqa: E402
from app import models as m  # noqa: E402
from app.services import investigation_service  # noqa: E402
from app.ml import predict as ml_predict  # noqa: E402

SAMPLE_SIZE = 300  # extra random transactions to investigate, beyond the demo cases


def main():
    ml_predict.load_models()
    db = SessionLocal()
    try:
        ids_to_run = set()

        # Always include the 5 guaranteed demo cases
        for fraud_type in ["account_takeover", "fraud_ring", "velocity_attack", "impossible_travel"]:
            txn = (
                db.query(m.Transaction)
                .filter(m.Transaction.fraud_type == fraud_type, m.Transaction.fraud_label == 1)
                .order_by(m.Transaction.amount.desc())
                .first()
            )
            if txn:
                ids_to_run.add(txn.id)

        legit = (
            db.query(m.Transaction)
            .filter(m.Transaction.fraud_type == "none", m.Transaction.amount.between(800, 3000))
            .order_by(m.Transaction.id.asc())
            .first()
        )
        if legit:
            ids_to_run.add(legit.id)

        # Add a random sample (mix of fraud + legit) for a populated dashboard
        all_ids = [row.id for row in db.query(m.Transaction.id).all()]
        random.seed(42)
        ids_to_run.update(random.sample(all_ids, min(SAMPLE_SIZE, len(all_ids))))

        print(f"Running {len(ids_to_run)} investigations...")
        for i, txn_id in enumerate(ids_to_run, 1):
            try:
                investigation_service.run_investigation(db, txn_id, force_rerun=False)
            except Exception as e:
                print(f"  failed on {txn_id}: {e}")
            if i % 25 == 0:
                print(f"  {i}/{len(ids_to_run)} done")

        print("\nDone. Dashboard should now show non-zero Flagged/Critical/Amount at Risk.")
    finally:
        db.close()


if __name__ == "__main__":
    main()