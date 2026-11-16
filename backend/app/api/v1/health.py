from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import Base
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(timestamp=datetime.now(UTC))


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness(request: Request, response: Response) -> ReadinessResponse:
    try:
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            tables = set(inspect(connection).get_table_names())
            schema_ready = set(Base.metadata.tables).issubset(tables)
        if not schema_ready:
            response.status_code = 503
        return ReadinessResponse(
            status="ready" if schema_ready else "not_ready",
            database="connected",
            schema_ready=schema_ready,
        )
    except SQLAlchemyError:
        # Never serialize database exceptions or connection details to clients.
        response.status_code = 503
        return ReadinessResponse(status="not_ready", database="unavailable", schema_ready=False)
