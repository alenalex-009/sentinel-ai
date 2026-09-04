"""Sentinel AI — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import district, habitations, risk, relocation, scenarios, data_status, validation
from app.core.config import settings

app = FastAPI(
    title="Sentinel AI API",
    description="GIS-first disaster decision-support platform — SIH PS 26191",
    version="0.4.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(district.router, prefix="/api/v1/districts", tags=["Districts"])
app.include_router(habitations.router, prefix="/api/v1/habitations", tags=["Habitations"])
app.include_router(risk.router, prefix="/api/v1/risk", tags=["Risk"])
app.include_router(relocation.router, prefix="/api/v1/relocation", tags=["Relocation"])
app.include_router(scenarios.router, prefix="/api/v1/scenarios", tags=["Scenarios"])
app.include_router(data_status.router, prefix="/api/v1/data-sources", tags=["Data Sources"])
app.include_router(validation.router, prefix="/api/v1/validate", tags=["Validation"])


@app.get("/health")
async def health_check():
    from app.db.database import check_db_health
    db = await check_db_health()
    return {
        "status": "ok",
        "service": "Sentinel AI API",
        "version": "0.4.0",
        "demo_mode": settings.DEMO_MODE,
        "database": db["status"],
        "database_message": db["message"],
    }


@app.get("/")
async def root():
    return {
        "message": "Sentinel AI — GIS Disaster Decision Support Platform",
        "version": "0.4.0",
        "docs": "/docs",
        "health": "/health",
        "validate": "/api/v1/validate/all",
    }
