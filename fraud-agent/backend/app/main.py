from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.ml import predict as ml_predict
from app.routers import (
    health, dashboard, transactions, investigations, network, cases, audit,
    model_metrics, demo,
)

app = FastAPI(
    title="AI Fraud Investigation Agent",
    description="Transaction -> ML Risk Score -> AI Investigation -> Evidence -> Risk Decision -> Human Review -> Audit",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # Create tables if they don't exist yet (idempotent). For production,
    # prefer running scripts/seed_database.py once against Supabase, which
    # also calls Base.metadata.create_all.
    Base.metadata.create_all(bind=engine)
    ml_predict.load_models()


app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(transactions.router)
app.include_router(investigations.router)
app.include_router(network.router)
app.include_router(cases.router)
app.include_router(audit.router)
app.include_router(model_metrics.router)
app.include_router(demo.router)


@app.get("/")
def root():
    return {
        "service": "AI Fraud Investigation Agent API",
        "status": "running",
        "docs": "/docs",
        "health": "/api/health",
    }
