from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from app import models  # noqa: F401 -- register all tables for readiness/migrations
from app.api.v1.health import health
from app.api.v1.router import router
from app.core.config import Settings
from app.db.session import create_db_engine
from app.schemas.health import HealthResponse


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    config = settings or Settings()
    database = engine if engine is not None else create_db_engine(config)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            yield
        finally:
            database.dispose()

    application = FastAPI(
        title="FraudSentinel API",
        description="Phase 1 foundation. Demo data is synthetic; risk is not proof of fraud.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if config.app_env != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if config.app_env != "production" else None,
    )
    application.state.settings = config
    application.state.engine = database
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    application.add_api_route("/health", health, response_model=HealthResponse, tags=["health"])
    application.include_router(router, prefix="/api/v1")
    return application


app = create_app()
