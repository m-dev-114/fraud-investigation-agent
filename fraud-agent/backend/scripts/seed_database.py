"""
Seeds the database (DATABASE_URL) with the generated synthetic CSVs.
Creates tables if they don't exist, then bulk-loads in FK-safe order.

Run:
  python scripts/generate_data.py     # first, if you haven't already
  python scripts/seed_database.py
"""
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.database import Base, engine, SessionLocal  # noqa: E402
from app import models as m  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic")

BOOL_COLS = {
    "customers": ["kyc_verified"],
    "devices": ["is_trusted"],
    "ip_events": ["is_vpn", "is_proxy"],
}
DATE_COLS = {
    "customers": ["account_created_at", "created_at"],
    "merchants": ["created_at"],
    "devices": ["first_seen_at", "last_seen_at"],
    "transactions": ["created_at"],
    "ip_events": ["event_at"],
    "disputes": ["filed_at", "resolved_at"],
}


def load_csv(name):
    path = os.path.join(DATA_DIR, f"{name}.csv")
    df = pd.read_csv(path)
    for col in DATE_COLS.get(name, []):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            df[col] = df[col].astype(object).where(df[col].notnull(), None)
    for col in BOOL_COLS.get(name, []):
        if col in df.columns:
            df[col] = df[col].astype(bool)
    df = df.where(pd.notnull(df), None)
    return df


def bulk_insert(session, model, df, batch_size=2000):
    records = df.to_dict(orient="records")
    total = len(records)
    for i in range(0, total, batch_size):
        batch = records[i:i + batch_size]
        session.bulk_insert_mappings(model, batch)
        session.commit()
        print(f"  {model.__tablename__}: {min(i + batch_size, total)}/{total}")


def main():
    print("Creating tables (idempotent)...")
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        for name, model in [
            ("customers", m.Customer),
            ("merchants", m.Merchant),
            ("devices", m.Device),
        ]:
            print(f"Loading {name}.csv...")
            df = load_csv(name)
            bulk_insert(session, model, df)

        print("Loading transactions.csv...")
        txns_df = load_csv("transactions")
        # ensure risk/investigation columns exist with sane defaults
        for col, default in [("risk_score", None), ("fraud_probability", None),
                              ("investigation_status", "not_started")]:
            if col not in txns_df.columns:
                txns_df[col] = default
        bulk_insert(session, m.Transaction, txns_df)

        print("Loading ip_events.csv...")
        ip_df = load_csv("ip_events")
        bulk_insert(session, m.IPEvent, ip_df)

        print("Loading disputes.csv...")
        disp_df = load_csv("disputes")
        bulk_insert(session, m.Dispute, disp_df)

        print("\nSeed complete.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
