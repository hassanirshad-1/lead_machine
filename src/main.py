"""Lead Machine — FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.campaigns import router as campaigns_api_router
from src.api.leads import router as leads_api_router
from src.dashboard.routes import router as dashboard_router
from src.database import Base, engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup (SQLite auto-creates the .db file)."""
    # Import all models so they are registered with Base
    import src.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables created / verified")
    yield
    # Shutdown
    await engine.dispose()


# Initialize FastAPI application
app = FastAPI(
    title="Outbound Lead Machine",
    description="Discover businesses without digital presence and feed the sales pipeline",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

# Mount static files (CSS, JS)
app.mount("/static", StaticFiles(directory="src/dashboard/static"), name="static")

# --- API Routes ---
app.include_router(campaigns_api_router)
app.include_router(leads_api_router)

# --- Dashboard Routes ---
app.include_router(dashboard_router)


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "message": "Lead Machine API is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)
