import uuid
import datetime as dt
from sqlalchemy import (
    Column, String, Float, Integer, Boolean, DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship
from app.database import Base


def gen_id(prefix: str):
    return lambda: f"{prefix}_{uuid.uuid4().hex[:12]}"


def now():
    return dt.datetime.utcnow()


class Customer(Base):
    __tablename__ = "customers"
    id = Column(String, primary_key=True, default=gen_id("cust"))
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String)
    city = Column(String)
    state = Column(String)
    country = Column(String, default="IN")
    account_created_at = Column(DateTime, default=now)
    risk_segment = Column(String, default="normal")  # normal, watchlist, high_risk
    kyc_verified = Column(Boolean, default=True)
    home_lat = Column(Float)
    home_lon = Column(Float)
    created_at = Column(DateTime, default=now)


class Merchant(Base):
    __tablename__ = "merchants"
    id = Column(String, primary_key=True, default=gen_id("merch"))
    name = Column(String, nullable=False)
    category = Column(String)
    mcc = Column(String)
    country = Column(String, default="IN")
    risk_rating = Column(String, default="low")  # low, medium, high
    avg_ticket_size = Column(Float, default=0.0)
    created_at = Column(DateTime, default=now)


class Device(Base):
    __tablename__ = "devices"
    id = Column(String, primary_key=True, default=gen_id("dev"))
    customer_id = Column(String, ForeignKey("customers.id"), index=True)
    device_fingerprint = Column(String, index=True)
    device_type = Column(String)
    os = Column(String)
    first_seen_at = Column(DateTime, default=now)
    last_seen_at = Column(DateTime, default=now)
    is_trusted = Column(Boolean, default=True)


class IPEvent(Base):
    __tablename__ = "ip_events"
    id = Column(String, primary_key=True, default=gen_id("ipev"))
    customer_id = Column(String, ForeignKey("customers.id"), index=True)
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True, nullable=True)
    ip_address = Column(String, index=True)
    ip_country = Column(String)
    city = Column(String)
    lat = Column(Float)
    lon = Column(Float)
    is_vpn = Column(Boolean, default=False)
    is_proxy = Column(Boolean, default=False)
    event_at = Column(DateTime, default=now)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(String, primary_key=True, default=gen_id("txn"))
    customer_id = Column(String, ForeignKey("customers.id"), index=True)
    merchant_id = Column(String, ForeignKey("merchants.id"), index=True)
    device_id = Column(String, ForeignKey("devices.id"), index=True, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    channel = Column(String, default="card")  # card, upi, netbanking, wallet
    status = Column(String, default="success")  # success, failed, pending
    txn_lat = Column(Float)
    txn_lon = Column(Float)
    txn_city = Column(String)
    txn_country = Column(String, default="IN")
    ip_address = Column(String)
    created_at = Column(DateTime, default=now, index=True)

    # labels (ground truth for synthetic data / model training)
    fraud_label = Column(Integer, default=0)  # 0/1
    fraud_type = Column(String, default="none")

    # ML / risk outputs (populated after prediction / investigation)
    risk_score = Column(Float, nullable=True)
    fraud_probability = Column(Float, nullable=True)
    investigation_status = Column(String, default="not_started")
    # not_started, in_progress, completed


class Dispute(Base):
    __tablename__ = "disputes"
    id = Column(String, primary_key=True, default=gen_id("disp"))
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True)
    customer_id = Column(String, ForeignKey("customers.id"), index=True)
    reason = Column(String)
    status = Column(String, default="open")  # open, resolved, rejected
    filed_at = Column(DateTime, default=now)
    resolved_at = Column(DateTime, nullable=True)


class Investigation(Base):
    __tablename__ = "investigations"
    id = Column(String, primary_key=True, default=gen_id("inv"))
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True)
    case_id = Column(String, ForeignKey("cases.id"), index=True, nullable=True)
    status = Column(String, default="running")  # running, completed, failed
    risk_score = Column(Float, nullable=True)
    fraud_probability = Column(Float, nullable=True)
    risk_level = Column(String, nullable=True)  # low, medium, high, critical
    recommendation = Column(String, nullable=True)  # approve, block, escalate
    summary = Column(Text, nullable=True)
    engine_used = Column(String, default="deterministic")  # deterministic | llm
    started_at = Column(DateTime, default=now)
    completed_at = Column(DateTime, nullable=True)


class InvestigationEvent(Base):
    __tablename__ = "investigation_events"
    id = Column(String, primary_key=True, default=gen_id("ievt"))
    investigation_id = Column(String, ForeignKey("investigations.id"), index=True)
    step = Column(String)  # e.g. "transaction_agent", "device_agent", ...
    event_type = Column(String)  # tool_call, tool_result, reasoning, decision
    title = Column(String)
    detail = Column(JSON, default=dict)
    created_at = Column(DateTime, default=now)


class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(String, primary_key=True, default=gen_id("evd"))
    investigation_id = Column(String, ForeignKey("investigations.id"), index=True)
    category = Column(String)  # velocity, device, network, geo, amount, account
    title = Column(String)
    description = Column(Text)
    severity = Column(String, default="low")  # low, medium, high, critical
    weight = Column(Float, default=0.0)
    raw_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=now)


class Case(Base):
    __tablename__ = "cases"
    id = Column(String, primary_key=True, default=gen_id("case"))
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True)
    customer_id = Column(String, ForeignKey("customers.id"), index=True)
    status = Column(String, default="open")  # open, closed
    priority = Column(String, default="medium")  # low, medium, high, critical
    created_at = Column(DateTime, default=now)
    closed_at = Column(DateTime, nullable=True)


class ModelPrediction(Base):
    __tablename__ = "model_predictions"
    id = Column(String, primary_key=True, default=gen_id("pred"))
    transaction_id = Column(String, ForeignKey("transactions.id"), index=True)
    model_name = Column(String)  # logistic_regression | xgboost
    model_version = Column(String)
    fraud_probability = Column(Float)
    predicted_label = Column(Integer)
    feature_snapshot = Column(JSON, default=dict)
    created_at = Column(DateTime, default=now)


class AnalystDecision(Base):
    __tablename__ = "analyst_decisions"
    id = Column(String, primary_key=True, default=gen_id("dec"))
    case_id = Column(String, ForeignKey("cases.id"), index=True)
    investigation_id = Column(String, ForeignKey("investigations.id"), index=True, nullable=True)
    analyst_name = Column(String, default="demo_analyst")
    decision = Column(String)  # approve, block, escalate
    notes = Column(Text, nullable=True)
    decided_at = Column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=gen_id("audit"))
    case_id = Column(String, ForeignKey("cases.id"), index=True, nullable=True)
    transaction_id = Column(String, nullable=True)
    actor = Column(String)  # system, agent:device, analyst, model
    action = Column(String)
    detail = Column(JSON, default=dict)
    created_at = Column(DateTime, default=now, index=True)
