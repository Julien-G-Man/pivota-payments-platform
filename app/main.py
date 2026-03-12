"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.lifespan import lifespan
from app.core.exceptions import (
    FloatMoneyError,
    WebhookSignatureError,
    DuplicateTransactionError,
    ComplianceHoldError,
)
from app.core.logging import configure_logging
from app.middleware.auth import jwt_auth_middleware
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

from app.domains.auth.router import router as auth_router
from app.domains.users.router import router as users_router
from app.domains.accounts.router import router as accounts_router
from app.domains.transactions.router import router as transactions_router
from app.domains.ingest.router import router as ingest_router
from app.domains.compliance.router import router as compliance_router
from app.domains.analytics.router import router as analytics_router
from app.domains.reports.router import router as reports_router
from app.domains.notifications.router import router as notifications_router
from app.domains.ai.router import router as ai_router


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="TraderFlow API",
        version="0.1.0",
        docs_url="/docs",      # Disabled in production via middleware
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Middleware (order matters — outermost first)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.middleware("http")(jwt_auth_middleware)

    # Routers
    api_v1 = "/api/v1"
    app.include_router(auth_router, prefix=f"{api_v1}/auth", tags=["auth"])
    app.include_router(users_router, prefix=f"{api_v1}/users", tags=["users"])
    app.include_router(accounts_router, prefix=f"{api_v1}/accounts", tags=["accounts"])
    app.include_router(transactions_router, prefix=f"{api_v1}/transactions", tags=["transactions"])
    app.include_router(ingest_router, prefix=f"{api_v1}", tags=["ingest"])
    app.include_router(compliance_router, prefix=f"{api_v1}/compliance", tags=["compliance"])
    app.include_router(analytics_router, prefix=f"{api_v1}/analytics", tags=["analytics"])
    app.include_router(reports_router, prefix=f"{api_v1}/reports", tags=["reports"])
    app.include_router(notifications_router, prefix=f"{api_v1}", tags=["notifications"])
    app.include_router(ai_router, prefix=f"{api_v1}/ai", tags=["ai"])

    # Exception handlers
    @app.exception_handler(FloatMoneyError)
    async def float_money_handler(request, exc):  # type: ignore[no-untyped-def]
        return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR"}})

    @app.exception_handler(WebhookSignatureError)
    async def webhook_sig_handler(request, exc):  # type: ignore[no-untyped-def]
        return JSONResponse(status_code=403, content={"error": {"code": "INVALID_SIGNATURE"}})

    @app.exception_handler(DuplicateTransactionError)
    async def duplicate_tx_handler(request, exc):  # type: ignore[no-untyped-def]
        return JSONResponse(status_code=200, content={"status": "duplicate"})

    @app.exception_handler(ComplianceHoldError)
    async def compliance_hold_handler(request, exc):  # type: ignore[no-untyped-def]
        return JSONResponse(status_code=422, content={"error": {"code": "COMPLIANCE_HOLD"}})

    @app.get("/health", tags=["health"])
    async def health() -> dict:  # type: ignore[type-arg]
        return {"status": "ok"}

    return app


app = create_app()
