"""
Basic API tests. Uses a temporary sqlite DB seeded with a handful of
hand-crafted records so tests are fast and don't depend on the full
100k-row synthetic dataset or a live Postgres instance.

Run:
  cd backend
  DATABASE_URL="sqlite:///./test.db" pytest tests/ -v
"""
import os
import sys
import datetime as dt

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.database import Base, engine, SessionLocal  # noqa: E402
from app import models as m  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    now = dt.datetime.utcnow()
    cust = m.Customer(
        id="cust_test1", full_name="Test User", email="test@example.com",
        city="Mumbai", state="Maharashtra", country="IN",
        account_created_at=now - dt.timedelta(days=400),
        risk_segment="normal", kyc_verified=True,
        home_lat=19.0760, home_lon=72.8777, created_at=now - dt.timedelta(days=400),
    )
    merch = m.Merchant(
        id="merch_test1", name="Test Merchant", category="Electronics", mcc="5732",
        country="IN", risk_rating="low", avg_ticket_size=2000, created_at=now,
    )
    txn_normal = m.Transaction(
        id="txn_test_normal", customer_id=cust.id, merchant_id=merch.id, device_id=None,
        amount=1200, currency="INR", channel="card", status="success",
        txn_lat=19.08, txn_lon=72.88, txn_city="Mumbai", txn_country="IN",
        ip_address="10.0.0.1", created_at=now, fraud_label=0, fraud_type="none",
    )
    txn_risky = m.Transaction(
        id="txn_test_risky", customer_id=cust.id, merchant_id=merch.id, device_id=None,
        amount=150000, currency="INR", channel="netbanking", status="success",
        txn_lat=25.2048, txn_lon=55.2708, txn_city="Dubai", txn_country="XX",
        ip_address="10.0.0.2", created_at=now, fraud_label=1, fraud_type="account_takeover",
    )
    db.add_all([cust, merch, txn_normal, txn_risky])
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    return TestClient(app)


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded")
    assert "db_connected" in body


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_list_transactions(client):
    resp = client.get("/api/transactions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 2
    assert len(body["items"]) >= 2


def test_get_transaction_detail(client):
    resp = client.get("/api/transactions/txn_test_normal")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "txn_test_normal"
    assert body["customer_name"] == "Test User"


def test_get_transaction_404(client):
    resp = client.get("/api/transactions/does_not_exist")
    assert resp.status_code == 404


def test_dashboard_summary(client):
    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_transactions"] >= 2


def test_run_investigation_risky_transaction_flags_high_risk(client):
    resp = client.post("/api/investigations/txn_test_risky/run", json={"force_rerun": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["risk_score"] > 40  # cross-border + huge amount + no device -> should be flagged
    assert body["recommendation"] in ("block", "escalate")
    assert len(body["evidence"]) > 0


def test_run_investigation_normal_transaction_low_risk(client):
    resp = client.post("/api/investigations/txn_test_normal/run", json={"force_rerun": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["risk_score"] < 50


def test_investigation_events_recorded(client):
    run_resp = client.post("/api/investigations/txn_test_risky/run", json={"force_rerun": True})
    inv_id = run_resp.json()["id"]
    resp = client.get(f"/api/investigations/{inv_id}/events")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) > 0
    steps = {e["step"] for e in events}
    assert "ml_risk_model" in steps
    assert "risk_decision_engine" in steps


def test_network_graph(client):
    resp = client.get("/api/network/txn_test_normal")
    assert resp.status_code == 200
    body = resp.json()
    assert any(n["type"] == "customer" for n in body["nodes"])
    assert any(n["type"] == "transaction" for n in body["nodes"])


def test_case_decision_flow(client):
    run_resp = client.post("/api/investigations/txn_test_risky/run", json={"force_rerun": True})
    case_id = run_resp.json()["case_id"]
    assert case_id is not None

    decision_resp = client.post(
        f"/api/cases/{case_id}/decision",
        json={"decision": "block", "analyst_name": "tester", "notes": "confirmed fraud"},
    )
    assert decision_resp.status_code == 200
    assert decision_resp.json()["decision"] == "block"

    audit_resp = client.get(f"/api/audit/{case_id}")
    assert audit_resp.status_code == 200
    actions = [a["action"] for a in audit_resp.json()]
    assert "decision_block" in actions


def test_case_decision_invalid_value_rejected(client):
    run_resp = client.post("/api/investigations/txn_test_risky/run", json={"force_rerun": True})
    case_id = run_resp.json()["case_id"]
    resp = client.post(f"/api/cases/{case_id}/decision", json={"decision": "not_a_real_decision"})
    assert resp.status_code == 400
