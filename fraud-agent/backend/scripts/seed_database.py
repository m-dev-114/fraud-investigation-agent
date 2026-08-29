"""
Seeds the database (DATABASE_URL) with the generated synthetic CSVs.
Creates tables if they don't exist, then bulk-loads in FK-safe order using
a raw psycopg2 connection with execute_values (fast, and avoids mixing
SQLAlchemy's session/connection pooling with a raw cursor).

Run:
  python scripts/generate_data.py     # first, if you haven't already
  python scripts/seed_database.py
"""
import os
import sys
import time
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.database import Base, engine  # noqa: E402
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


def bulk_insert(raw_conn, model, df, batch_size=2000, max_retries=5):
    """Uses a raw psycopg2 connection + execute_values for fast batched
    inserts. Reconnects on failure so a dropped connection doesn't kill
    the whole run."""
    from psycopg2.extras import execute_values

    records = df.to_dict(orient="records")
    total = len(records)
    if total == 0:
        return raw_conn

    table = model.__table__
    columns = [c.name for c in table.columns if c.name in df.columns]
    col_list = ", ".join(columns)
    insert_sql = f"INSERT INTO {table.name} ({col_list}) VALUES %s"

    for i in range(0, total, batch_size):
        batch = records[i:i + batch_size]
        values = [tuple(row.get(col) for col in columns) for row in batch]

        for attempt in range(1, max_retries + 1):
            try:
                cursor = raw_conn.cursor()
                execute_values(cursor, insert_sql, values, page_size=batch_size)
                raw_conn.commit()
                cursor.close()
                break
            except Exception as e:
                try:
                    raw_conn.rollback()
                    raw_conn.close()
                except Exception:
                    pass
                if attempt == max_retries:
                    raise
                wait = attempt * 3
                print(f"  retrying batch {i} (attempt {attempt}) after error: {e}")
                time.sleep(wait)
                raw_conn = engine.raw_connection()  # fresh connection
        print(f"  {model.__tablename__}: {min(i + batch_size, total)}/{total}")

    return raw_conn


def main():
    print("Creating tables (idempotent)...")
    Base.metadata.create_all(bind=engine)

    raw_conn = engine.raw_connection()
    try:
        for name, model in [
            ("customers", m.Customer),
            ("merchants", m.Merchant),
            ("devices", m.Device),
        ]:
            print(f"Loading {name}.csv...")
            df = load_csv(name)
            raw_conn = bulk_insert(raw_conn, model, df)

        print("Loading transactions.csv...")
        txns_df = load_csv("transactions")
        for col, default in [("risk_score", None), ("fraud_probability", None),
                              ("investigation_status", "not_started")]:
            if col not in txns_df.columns:
                txns_df[col] = default
        raw_conn = bulk_insert(raw_conn, m.Transaction, txns_df)

        print("Loading ip_events.csv...")
        ip_df = load_csv("ip_events")
        valid_txn_ids = set(txns_df["id"])
        before = len(ip_df)
        ip_df = ip_df[ip_df["transaction_id"].isna() | ip_df["transaction_id"].isin(valid_txn_ids)]
        print(f"  filtered out {before - len(ip_df)} ip_events rows with orphaned transaction_id")
        raw_conn = bulk_insert(raw_conn, m.IPEvent, ip_df)

        print("Loading disputes.csv...")
        disp_df = load_csv("disputes")
        before = len(disp_df)
        disp_df = disp_df[disp_df["transaction_id"].isna() | disp_df["transaction_id"].isin(valid_txn_ids)]
        print(f"  filtered out {before - len(disp_df)} disputes rows with orphaned transaction_id")
        raw_conn = bulk_insert(raw_conn, m.Dispute, disp_df)
        print("\nSeed complete.")
    finally:
        raw_conn.close()


if __name__ == "__main__":
    main()
