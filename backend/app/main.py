import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.bill_verification import log_bill_verification
from app.congress_client import CongressClient
from app.config import settings
from app.admin_store import init_admin_db
from app.analytics_store import init_analytics_db
from app.users_store import init_users_db
from app.routes import (
    accounts,
    admin,
    analytics,
    board,
    health,
    involve,
    members,
    metrics,
    public_api,
)
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
        init_admin_db()
    except Exception:
        # Login would fail closed; the public site must still serve.
        logger.exception("Admin database init failed")
    try:
        init_users_db()
    except Exception:
        logger.exception("User database init failed (non-fatal)")
    try:
        from app.observability import configure_logging, init_tracing

        configure_logging()
        init_tracing(app)
    except Exception:
        logger.exception("Observability init failed (non-fatal)")
    try:
        if settings.scheduler_enabled:
            from app.jobs import start_scheduler

            start_scheduler()
    except Exception:
        logger.exception("Background scheduler failed to start (non-fatal)")
    try:
        if settings.skip_bill_verification:
            logger.info("Skipping tracked bill verification (SKIP_BILL_VERIFICATION=1)")
        else:
            await log_bill_verification(app.state.congress_client)
    except Exception:
        # Non-fatal: verification needs a live Congress.gov and an API key.
        # Failing closed here would turn an upstream hiccup into an outage.
        logger.exception("Tracked bill verification failed at startup (non-fatal)")
    yield
    try:
        from app.jobs import stop_scheduler

        stop_scheduler()
    except Exception:
        logger.exception("Failed to stop background scheduler")
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
app.include_router(accounts.router, prefix="/api")
app.include_router(board.router, prefix="/api")
app.include_router(public_api.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
