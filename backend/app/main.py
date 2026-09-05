from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(
    title="SLPHC 2026 Logistics Command & Asset Management System",
    version="1.0.0",
    description="End-to-end census asset accountability: source to final receiver, "
    "field custodian, return and disposition.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
