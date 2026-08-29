"""
Feature engineering for fraud scoring.
Used both by the offline training script and the online prediction service,
so feature definitions never drift between train and serve.
"""
import numpy as np
import pandas as pd
from math import radians, sin, cos, sqrt, atan2

FEATURE_COLUMNS = [
    "amount",
    "amount_log",
    "amount_zscore_vs_customer",
    "hour_of_day",
    "is_night",
    "is_weekend",
    "channel_card", "channel_upi", "channel_netbanking", "channel_wallet",
    "is_new_device",
    "is_foreign_txn",
    "merchant_risk_high", "merchant_risk_medium",
    "customer_watchlist", "customer_high_risk",
    "customer_kyc_verified",
    "account_age_days",
    "velocity_txn_count_1h",
    "velocity_amount_sum_1h",
    "distance_from_home_km",
    "distance_from_prev_txn_km",
    "minutes_since_prev_txn",
    "implied_speed_kmh",
    "shared_ip_customer_count",
    "shared_device_customer_count",
    "recent_failed_txn_count_1h",
]


def haversine_km(lat1, lon1, lat2, lon2):
    if any(pd.isna([lat1, lon1, lat2, lon2])):
        return 0.0
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def build_features(transactions: pd.DataFrame, customers: pd.DataFrame,
                    merchants: pd.DataFrame, devices: pd.DataFrame) -> pd.DataFrame:
    """
    transactions: must include id, customer_id, merchant_id, device_id, amount,
                   channel, txn_lat, txn_lon, txn_country, ip_address, created_at, status
    Returns a DataFrame indexed the same as `transactions` with FEATURE_COLUMNS.
    """
    df = transactions.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.sort_values(["customer_id", "created_at"]).reset_index(drop=True)

    cust = customers.set_index("id")
    merch = merchants.set_index("id")
    dev_known = set(devices["id"]) if devices is not None and len(devices) else set()

    # --- customer-level stats (historical average, computed causally) -------
    df["amount_log"] = np.log1p(df["amount"])

    # per-customer expanding mean/std of amount (causal, uses prior txns only)
    df["_cust_running_mean"] = (
        df.groupby("customer_id")["amount"].transform(lambda s: s.expanding().mean().shift(1))
    )
    df["_cust_running_std"] = (
        df.groupby("customer_id")["amount"].transform(lambda s: s.expanding().std().shift(1))
    )
    global_mean, global_std = df["amount"].mean(), df["amount"].std()
    df["_cust_running_mean"] = df["_cust_running_mean"].fillna(global_mean)
    df["_cust_running_std"] = df["_cust_running_std"].fillna(global_std).replace(0, global_std)
    df["amount_zscore_vs_customer"] = (df["amount"] - df["_cust_running_mean"]) / df["_cust_running_std"]

    df["hour_of_day"] = df["created_at"].dt.hour
    df["is_night"] = df["hour_of_day"].apply(lambda h: 1 if (h >= 23 or h <= 5) else 0)
    df["is_weekend"] = df["created_at"].dt.dayofweek.isin([5, 6]).astype(int)

    for ch in ["card", "upi", "netbanking", "wallet"]:
        df[f"channel_{ch}"] = (df["channel"] == ch).astype(int)

    df["is_new_device"] = df["device_id"].apply(lambda d: 0 if (pd.notna(d) and d in dev_known) else 1)
    df["is_foreign_txn"] = (df["txn_country"] != "IN").astype(int)

    df["_merch_risk"] = df["merchant_id"].map(lambda m: merch["risk_rating"].get(m, "low") if m in merch.index else "low")
    df["merchant_risk_high"] = (df["_merch_risk"] == "high").astype(int)
    df["merchant_risk_medium"] = (df["_merch_risk"] == "medium").astype(int)

    df["_cust_segment"] = df["customer_id"].map(lambda c: cust["risk_segment"].get(c, "normal") if c in cust.index else "normal")
    df["customer_watchlist"] = (df["_cust_segment"] == "watchlist").astype(int)
    df["customer_high_risk"] = (df["_cust_segment"] == "high_risk").astype(int)
    df["customer_kyc_verified"] = df["customer_id"].map(
        lambda c: int(bool(cust["kyc_verified"].get(c, True))) if c in cust.index else 1
    )

    def _acct_age(row):
        if row["customer_id"] in cust.index:
            created = pd.to_datetime(cust.loc[row["customer_id"], "account_created_at"])
            return max((row["created_at"] - created).days, 0)
        return 0
    df["account_age_days"] = df.apply(_acct_age, axis=1)

    # --- velocity features (causal: only prior txns within trailing window) --
    df = df.set_index("created_at", drop=False)
    vel_counts = []
    vel_sums = []
    fail_counts = []
    for cid, g in df.groupby("customer_id"):
        g = g.sort_index()
        cnt = g["amount"].rolling("1h").count() - 1  # exclude current txn
        amt = g["amount"].rolling("1h").sum() - g["amount"]
        vel_counts.append(cnt)
        vel_sums.append(amt)
        fail = g["status"].apply(lambda s: 1 if s == "failed" else 0)
        fail_roll = fail.rolling("1h").sum() - fail
        fail_counts.append(fail_roll)
    df["velocity_txn_count_1h"] = pd.concat(vel_counts).clip(lower=0)
    df["velocity_amount_sum_1h"] = pd.concat(vel_sums).clip(lower=0)
    df["recent_failed_txn_count_1h"] = pd.concat(fail_counts).clip(lower=0)
    df = df.reset_index(drop=True)

    # --- geo features ---------------------------------------------------------
    def _dist_home(row):
        if row["customer_id"] in cust.index:
            hlat, hlon = cust.loc[row["customer_id"], ["home_lat", "home_lon"]]
            return haversine_km(row["txn_lat"], row["txn_lon"], hlat, hlon)
        return 0.0
    df["distance_from_home_km"] = df.apply(_dist_home, axis=1)

    df["_prev_lat"] = df.groupby("customer_id")["txn_lat"].shift(1)
    df["_prev_lon"] = df.groupby("customer_id")["txn_lon"].shift(1)
    df["_prev_time"] = df.groupby("customer_id")["created_at"].shift(1)
    df["distance_from_prev_txn_km"] = df.apply(
        lambda r: haversine_km(r["txn_lat"], r["txn_lon"], r["_prev_lat"], r["_prev_lon"])
        if pd.notna(r["_prev_lat"]) else 0.0, axis=1
    )
    df["minutes_since_prev_txn"] = df.apply(
        lambda r: max((r["created_at"] - r["_prev_time"]).total_seconds() / 60.0, 0.01)
        if pd.notna(r["_prev_time"]) else 999999.0, axis=1
    )
    df["implied_speed_kmh"] = df["distance_from_prev_txn_km"] / (df["minutes_since_prev_txn"] / 60.0)
    df["implied_speed_kmh"] = df["implied_speed_kmh"].replace([np.inf, -np.inf], 0).fillna(0)

    # --- shared ip / device fan-out (how many distinct customers used this
    #     same ip/device across the whole dataset — proxy for ring detection) ---
    ip_fanout = df.groupby("ip_address")["customer_id"].transform("nunique")
    df["shared_ip_customer_count"] = ip_fanout
    dev_fanout = df.groupby("device_id")["customer_id"].transform("nunique")
    df["shared_device_customer_count"] = dev_fanout.fillna(1)

    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    result = df[["id"] + FEATURE_COLUMNS].copy()
    return result
