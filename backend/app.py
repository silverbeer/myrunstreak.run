"""FastAPI entry point — replaces the Lambda + API Gateway stack."""

import logging

from backend.config import get_settings
from backend.routes import auth_routes, metrics, runs, stats, sync
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    app = FastAPI(
        title="myrunstreak API",
        version="0.1.0",
        description="Backend for myrunstreak.run",
    )

    # CORS: bearer-token auth (no cookies) → "*" is safe.
    origins = (
        ["*"]
        if settings.cors_allow_origins.strip() == "*"
        else [o.strip() for o in settings.cors_allow_origins.split(",")]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Api-Key"],
        max_age=300,
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(stats.router)
    app.include_router(runs.router)
    app.include_router(sync.router)
    app.include_router(auth_routes.router)
    app.include_router(metrics.router)

    return app


app = create_app()
