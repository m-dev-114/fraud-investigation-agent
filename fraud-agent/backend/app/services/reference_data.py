import time
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

_cache = {"data": None, "ts": 0}
TTL_SECONDS = 60


def get_reference_frames(db: Session):
    """Returns (customers_df, merchants_df, devices_df), cached briefly to
    avoid re-querying the whole table on every single investigation call."""
    now = time.time()
    if _cache["data"] is not None and (now - _cache["ts"]) < TTL_SECONDS:
        return _cache["data"]

    customers_df = pd.read_sql(text("SELECT * FROM customers"), db.bind)
    merchants_df = pd.read_sql(text("SELECT * FROM merchants"), db.bind)
    devices_df = pd.read_sql(text("SELECT * FROM devices"), db.bind)

    data = (customers_df, merchants_df, devices_df)
    _cache["data"] = data
    _cache["ts"] = now
    return data


def invalidate_cache():
    _cache["data"] = None
    _cache["ts"] = 0
