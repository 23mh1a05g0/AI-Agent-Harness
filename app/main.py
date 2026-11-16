"""Main FastAPI Application Entrypoint."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base, SessionLocal
from app.api import agent_router, hitl_router, system_router
from app.services.trust_service import trust_service

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger("ai_agent_harness")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context: initialize database tables and trust store defaults."""
    logger.info("Initializing database schemas...")
    try:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            for tool in ["purge", "mark_posted"]:
                trust_service.get_or_create(db, tool)
        logger.info(f"{settings.APP_NAME} initialized successfully.")
    except Exception as ex:
        logger.warning(f"Database schema initialization warning (will retry on request): {ex}")
    yield
    logger.info("Application shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Trust-Based Progressive Autonomy with Human-in-the-Loop Guardrails",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(agent_router)
app.include_router(hitl_router)
app.include_router(system_router)


@app.get("/", tags=["System"])
def api_welcome():
    """Welcome endpoint with service information."""
    return {
        "name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "status": "online",
        "mock_llm_enabled": settings.MOCK_LLM_ENABLED,
        "trust_threshold": settings.TRUST_THRESHOLD,
        "documentation": "/docs",
    }


@app.get("/health", tags=["System"])
def health_check():
    """Service health check endpoint."""
    return {
        "status": "healthy",
        "database": "connected",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.API_PORT, reload=settings.DEBUG)
