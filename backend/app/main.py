import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bill_verification import log_bill_verification
from app.congress_client import CongressClient
from app.config import settings
from app.analytics_store import init_analytics_db
from app.routes import analytics, health, involve, members, metrics
from app.security import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)

_IS_PROD = os.environ.get("ENV", os.environ.get("APP_ENV", "")).lower() in {
    "prod",
    "production",
} or os.environ.get("DISABLE_API_DOCS", "").lower() in {"1", "true", "yes"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.congress_client = CongressClient()
    try:
        init_analytics_db()
    except Exception:
        logger.exception("Analytics database init failed (non-fatal)")
    try:
        await log_bill_verification(app.state.congress_client)
    except Exception:
        # Non-fatal: verification needs a live Congress.gov and an API key.
        # Failing closed here would turn an upstream hiccup into an outage.
        logger.exception("Tracked bill verification failed at startup (non-fatal)")
    yield
    await app.state.congress_client.close()


app = FastAPI(
    title="Operation Child Shield API",
    description="Transparency API for child protection voting records from Congress.gov",
    version="1.0.0",
    lifespan=lifespan,
    # Hide OpenAPI UI in production even if the backend is ever exposed directly.
    docs_url=None if _IS_PROD else "/docs",
    redoc_url=None if _IS_PROD else "/redoc",
    openapi_url=None if _IS_PROD else "/openapi.json",
)

# CORS first (outermost last-added runs first in Starlette); security headers next.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # No cookies or auth headers are used; keeping credentials off avoids
    # granting cross-origin authenticated access if cookies are added later.
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)

app.include_router(health.router, prefix="/api")
app.include_router(members.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(involve.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
