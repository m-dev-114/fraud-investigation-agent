import datetime as dt
from typing import Optional, List, Any, Dict
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    env: str
    db_connected: bool
    model_loaded: bool


class DashboardSummary(BaseModel):
    total_transactions: int
    flagged_transactions: int
    critical_transactions: int
    fraud_rate: float
    amount_at_risk: float
    total_amount: float
    transactions_by_day: List[Dict[str, Any]]
    fraud_by_type: List[Dict[str, Any]]
    risk_distribution: List[Dict[str, Any]]
    recent_investigations: List[Dict[str, Any]]


class TransactionOut(BaseModel):
    id: str
    customer_id: str
    merchant_id: str
    amount: float
    currency: str
    channel: str
    status: str
    txn_city: Optional[str] = None
    txn_country: Optional[str] = None
    created_at: dt.datetime
    fraud_label: int
    fraud_type: str
    risk_score: Optional[float] = None
    fraud_probability: Optional[float] = None
    investigation_status: str

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    items: List[TransactionOut]
    total: int
    page: int
    page_size: int


class TransactionDetail(TransactionOut):
    customer_name: Optional[str] = None
    merchant_name: Optional[str] = None
    device_id: Optional[str] = None
    ip_address: Optional[str] = None


class RunInvestigationRequest(BaseModel):
    force_rerun: bool = False


class InvestigationEventOut(BaseModel):
    id: str
    step: str
    event_type: str
    title: str
    detail: Dict[str, Any]
    created_at: dt.datetime

    class Config:
        from_attributes = True


class EvidenceOut(BaseModel):
    id: str
    category: str
    title: str
    description: str
    severity: str
    weight: float
    raw_data: Dict[str, Any]

    class Config:
        from_attributes = True


class InvestigationOut(BaseModel):
    id: str
    transaction_id: str
    case_id: Optional[str] = None
    status: str
    risk_score: Optional[float] = None
    fraud_probability: Optional[float] = None
    risk_level: Optional[str] = None
    recommendation: Optional[str] = None
    summary: Optional[str] = None
    engine_used: str
    started_at: dt.datetime
    completed_at: Optional[dt.datetime] = None
    evidence: List[EvidenceOut] = []

    class Config:
        from_attributes = True


class NetworkNode(BaseModel):
    id: str
    type: str  # customer, device, ip, merchant, transaction
    label: str
    risk: Optional[str] = None
    data: Dict[str, Any] = {}


class NetworkEdge(BaseModel):
    id: str
    source: str
    target: str
    label: Optional[str] = None


class NetworkGraph(BaseModel):
    nodes: List[NetworkNode]
    edges: List[NetworkEdge]


class DecisionRequest(BaseModel):
    decision: str  # approve, block, escalate
    analyst_name: str = "demo_analyst"
    notes: Optional[str] = None


class DecisionOut(BaseModel):
    id: str
    case_id: str
    decision: str
    analyst_name: str
    notes: Optional[str] = None
    decided_at: dt.datetime

    class Config:
        from_attributes = True


class AuditLogOut(BaseModel):
    id: str
    actor: str
    action: str
    detail: Dict[str, Any]
    created_at: dt.datetime

    class Config:
        from_attributes = True


class ModelMetrics(BaseModel):
    model_name: str
    trained_at: Optional[str] = None
    n_train: int
    n_test: int
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    confusion_matrix: Dict[str, int]
    feature_importance: List[Dict[str, Any]] = []


class ModelMetricsResponse(BaseModel):
    logistic_regression: Optional[ModelMetrics] = None
    xgboost: Optional[ModelMetrics] = None
