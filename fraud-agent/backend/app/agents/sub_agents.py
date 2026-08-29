"""
Deterministic investigation sub-agents. Each agent queries Supabase (via the
SQLAlchemy session) for a specific slice of context and returns a list of
evidence dicts: {category, title, description, severity, weight, raw_data}.

severity: low | medium | high | critical
weight:   0-30 contribution to the final 0-100 risk score

These agents are intentionally rule + data driven so the system produces a
result even with LLM_API_KEY unset. The optional LLM layer (see
app/agents/llm_explainer.py) only narrates/explains this evidence — it never
alters weights or the resulting recommendation.
"""
import datetime as dt
from math import radians, sin, cos, sqrt, atan2
from sqlalchemy import func
from sqlalchemy.orm import Session
from app import models as m


def haversine_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return 0.0
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def transaction_agent(db: Session, txn: m.Transaction, customer_history):
    """Looks at the transaction's amount relative to the customer's typical spend."""
    evidence = []
    amounts = [t.amount for t in customer_history if t.id != txn.id and t.created_at < txn.created_at]
    if amounts:
        avg = sum(amounts) / len(amounts)
        mx = max(amounts)
        if txn.amount > max(avg * 5, mx * 1.5) and txn.amount > 10000:
            evidence.append({
                "category": "amount", "title": "Amount far exceeds customer baseline",
                "description": (
                    f"Transaction amount ₹{txn.amount:,.2f} is {txn.amount / avg:.1f}x the "
                    f"customer's historical average of ₹{avg:,.2f} (n={len(amounts)} prior txns, "
                    f"max prior ₹{mx:,.2f})."
                ),
                "severity": "high" if txn.amount > avg * 10 else "medium",
                "weight": 18 if txn.amount > avg * 10 else 10,
                "raw_data": {"amount": txn.amount, "customer_avg": avg, "customer_max": mx},
            })
    else:
        if txn.amount > 20000:
            evidence.append({
                "category": "amount", "title": "High-value transaction with no prior history",
                "description": f"₹{txn.amount:,.2f} transaction from a customer with no prior transaction history to compare against.",
                "severity": "medium", "weight": 8,
                "raw_data": {"amount": txn.amount},
            })
    if txn.status == "failed":
        evidence.append({
            "category": "amount", "title": "Transaction failed authorization",
            "description": "This transaction was declined/failed at authorization.",
            "severity": "low", "weight": 2, "raw_data": {"status": txn.status},
        })
    return evidence


def velocity_agent(db: Session, txn: m.Transaction):
    """Counts recent transactions/failures by this customer in a trailing window."""
    evidence = []
    window_start = txn.created_at - dt.timedelta(hours=1)
    recent = db.query(m.Transaction).filter(
        m.Transaction.customer_id == txn.customer_id,
        m.Transaction.created_at >= window_start,
        m.Transaction.created_at <= txn.created_at,
        m.Transaction.id != txn.id,
    ).all()
    if len(recent) >= 4:
        total = sum(t.amount for t in recent) + txn.amount
        evidence.append({
            "category": "velocity", "title": "High transaction velocity",
            "description": (
                f"{len(recent) + 1} transactions from this customer within a 1-hour window "
                f"totaling ₹{total:,.2f}."
            ),
            "severity": "critical" if len(recent) >= 8 else "high",
            "weight": 22 if len(recent) >= 8 else 14,
            "raw_data": {"count_1h": len(recent) + 1, "sum_1h": total},
        })
    failed_recent = [t for t in recent if t.status == "failed"]
    if len(failed_recent) >= 3:
        evidence.append({
            "category": "velocity", "title": "Card-testing pattern detected",
            "description": (
                f"{len(failed_recent)} failed low-value authorization attempts immediately "
                f"preceded this transaction — consistent with automated card testing."
            ),
            "severity": "critical", "weight": 20,
            "raw_data": {"failed_count_1h": len(failed_recent)},
        })
    return evidence


def device_agent(db: Session, txn: m.Transaction):
    evidence = []
    if txn.device_id is None:
        evidence.append({
            "category": "device", "title": "Unrecognized or missing device",
            "description": "This transaction was not linked to any device previously associated with the customer's account.",
            "severity": "medium", "weight": 10,
            "raw_data": {"device_id": None},
        })
        return evidence

    device = db.query(m.Device).filter(m.Device.id == txn.device_id).first()
    if device is None:
        return evidence

    if device.customer_id != txn.customer_id:
        evidence.append({
            "category": "device", "title": "Device belongs to a different account",
            "description": "The device used for this transaction is registered to a different customer.",
            "severity": "critical", "weight": 20,
            "raw_data": {"device_owner": device.customer_id},
        })

    distinct_customers = db.query(func.count(func.distinct(m.Transaction.customer_id))).filter(
        m.Transaction.device_id == device.id
    ).scalar()
    if distinct_customers and distinct_customers >= 3:
        evidence.append({
            "category": "device", "title": "Device shared across multiple accounts",
            "description": f"This device has been used by {distinct_customers} distinct customer accounts.",
            "severity": "critical" if distinct_customers >= 5 else "high",
            "weight": 20 if distinct_customers >= 5 else 14,
            "raw_data": {"distinct_customers": distinct_customers},
        })

    if not device.is_trusted:
        evidence.append({
            "category": "device", "title": "Device flagged as untrusted",
            "description": "This device fingerprint is marked untrusted based on prior activity.",
            "severity": "medium", "weight": 8, "raw_data": {"is_trusted": False},
        })
    return evidence


def merchant_agent(db: Session, txn: m.Transaction):
    evidence = []
    merchant = db.query(m.Merchant).filter(m.Merchant.id == txn.merchant_id).first()
    if merchant is None:
        return evidence
    if merchant.risk_rating == "high":
        evidence.append({
            "category": "merchant", "title": "High-risk merchant category",
            "description": f"Merchant '{merchant.name}' ({merchant.category}) is rated high-risk (MCC {merchant.mcc}).",
            "severity": "medium", "weight": 8,
            "raw_data": {"merchant": merchant.name, "category": merchant.category},
        })
    elif merchant.risk_rating == "medium":
        evidence.append({
            "category": "merchant", "title": "Elevated-risk merchant category",
            "description": f"Merchant '{merchant.name}' ({merchant.category}) carries elevated risk rating.",
            "severity": "low", "weight": 4,
            "raw_data": {"merchant": merchant.name, "category": merchant.category},
        })
    return evidence


def network_location_agent(db: Session, txn: m.Transaction, customer: m.Customer):
    evidence = []

    # distance from home
    if customer.home_lat is not None and txn.txn_lat is not None:
        dist_home = haversine_km(txn.txn_lat, txn.txn_lon, customer.home_lat, customer.home_lon)
        if dist_home > 500:
            evidence.append({
                "category": "network", "title": "Transaction far from customer's home location",
                "description": f"Transaction occurred {dist_home:,.0f} km from the customer's registered home city.",
                "severity": "high" if dist_home > 3000 else "medium",
                "weight": 14 if dist_home > 3000 else 8,
                "raw_data": {"distance_from_home_km": dist_home},
            })

    if txn.txn_country and txn.txn_country != "IN":
        evidence.append({
            "category": "network", "title": "Cross-border transaction",
            "description": f"Transaction originated outside India (country code: {txn.txn_country}).",
            "severity": "high", "weight": 12,
            "raw_data": {"country": txn.txn_country},
        })

    # impossible travel: compare with immediately prior transaction
    prev_txn = db.query(m.Transaction).filter(
        m.Transaction.customer_id == txn.customer_id,
        m.Transaction.created_at < txn.created_at,
    ).order_by(m.Transaction.created_at.desc()).first()
    if prev_txn and prev_txn.txn_lat is not None and txn.txn_lat is not None:
        dist = haversine_km(txn.txn_lat, txn.txn_lon, prev_txn.txn_lat, prev_txn.txn_lon)
        minutes = max((txn.created_at - prev_txn.created_at).total_seconds() / 60.0, 0.01)
        speed = dist / (minutes / 60.0)
        if dist > 100 and speed > 900:  # faster than a commercial flight average
            evidence.append({
                "category": "network", "title": "Impossible travel detected",
                "description": (
                    f"Previous transaction was {dist:,.0f} km away, only {minutes:.0f} minutes earlier "
                    f"— implies travel speed of {speed:,.0f} km/h, which is not physically possible."
                ),
                "severity": "critical", "weight": 22,
                "raw_data": {"distance_km": dist, "minutes_gap": minutes, "implied_speed_kmh": speed},
            })

    # shared IP fan-out
    if txn.ip_address:
        distinct_customers = db.query(func.count(func.distinct(m.IPEvent.customer_id))).filter(
            m.IPEvent.ip_address == txn.ip_address
        ).scalar()
        if distinct_customers and distinct_customers >= 3:
            evidence.append({
                "category": "network", "title": "IP address shared across multiple accounts",
                "description": f"IP address {txn.ip_address} has been used by {distinct_customers} distinct customer accounts — consistent with a coordinated fraud ring.",
                "severity": "critical" if distinct_customers >= 5 else "high",
                "weight": 20 if distinct_customers >= 5 else 13,
                "raw_data": {"ip": txn.ip_address, "distinct_customers": distinct_customers},
            })

    return evidence


def customer_agent(db: Session, customer: m.Customer, txn: m.Transaction):
    evidence = []
    if customer.risk_segment == "high_risk":
        evidence.append({
            "category": "account", "title": "Customer on high-risk segment",
            "description": "This customer's account is internally flagged as high-risk.",
            "severity": "high", "weight": 12, "raw_data": {"risk_segment": "high_risk"},
        })
    elif customer.risk_segment == "watchlist":
        evidence.append({
            "category": "account", "title": "Customer on internal watchlist",
            "description": "This customer's account is on the internal fraud watchlist.",
            "severity": "medium", "weight": 7, "raw_data": {"risk_segment": "watchlist"},
        })
    if not customer.kyc_verified:
        evidence.append({
            "category": "account", "title": "KYC not verified",
            "description": "This customer's account does not have completed KYC verification.",
            "severity": "medium", "weight": 6, "raw_data": {"kyc_verified": False},
        })
    account_age_days = (txn.created_at - customer.account_created_at).days if customer.account_created_at else None
    if account_age_days is not None and account_age_days < 7 and txn.amount > 10000:
        evidence.append({
            "category": "account", "title": "New account, high-value transaction",
            "description": f"Account is only {account_age_days} day(s) old and already transacting ₹{txn.amount:,.2f}.",
            "severity": "high", "weight": 12,
            "raw_data": {"account_age_days": account_age_days},
        })
    open_disputes = db.query(m.Dispute).filter(
        m.Dispute.customer_id == customer.id, m.Dispute.status == "open"
    ).count()
    if open_disputes:
        evidence.append({
            "category": "account", "title": "Customer has open disputes",
            "description": f"This customer has {open_disputes} open dispute(s) on file.",
            "severity": "medium", "weight": 6, "raw_data": {"open_disputes": open_disputes},
        })
    return evidence
