from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import models  # noqa: F401 -- register all tables for readiness/migrations
from app.api.v1.health import health
from app.api.v1.intelligence import validate_sandbox_engine
from app.api.v1.router import router
from app.core.config import Settings
from app.core.request_limits import InvestigationRequestLimits
from app.db.session import create_db_engine
from app.repositories.intelligence import AccessDenied, Conflict, ResourceNotFound
from app.schemas.health import HealthResponse
from app.services.detection import Rules


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    config = settings or Settings()
    database = engine if engine is not None else create_db_engine(config)
    validate_sandbox_engine(config, database)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            yield
        finally:
            database.dispose()

    application = FastAPI(
        title="FraudSentinel API",
        description=(
            "Foundation and isolated synthetic investigations. "
            "Risk signals are not proof of fraud; production identity is not implemented."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if config.app_env != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if config.app_env != "production" else None,
    )
    application.state.settings = config
    application.state.engine = database
    application.add_middleware(InvestigationRequestLimits)
    application.state.scoring_rules = (
        Rules.model_validate_json(config.scoring_rules_path.read_text())
        if config.scoring_rules_path
        else Rules()
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"] if config.investigation_sandbox else ["GET"],
        allow_headers=["Content-Type", "X-FraudSentinel-Sandbox"]
        if config.investigation_sandbox
        else ["Content-Type"],
    )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": list(e["loc"]), "type": e["type"], "msg": "Invalid request value"}
                    for e in exc.errors()
                ]
            },
        )

    @application.exception_handler(AccessDenied)
    async def denied(request: Request, exc: AccessDenied):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @application.exception_handler(ResourceNotFound)
    async def missing(request: Request, exc: ResourceNotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(Conflict)
    async def conflict(request: Request, exc: Conflict):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(IntegrityError)
    async def integrity(request: Request, exc: IntegrityError):
        return JSONResponse(
            status_code=409, content={"detail": "Record conflict; refresh before retrying"}
        )

    application.add_api_route("/health", health, response_model=HealthResponse, tags=["health"])
    application.include_router(router, prefix="/api/v1")
    return application


app = create_app()
