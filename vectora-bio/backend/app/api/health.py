"""Service health and data availability."""

from fastapi import APIRouter
from sqlalchemy.engine import make_url

from app.api.deps import DbSession, SettingsDep, StoreDep
from app.errors import DatabaseUnavailableError
from app.schemas.health import DatabaseStatus, HealthResponse
from app.services import metadata_service

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Service, database, and dataset status")
def health(db: DbSession, settings: SettingsDep, store: StoreDep) -> HealthResponse:
    dialect = make_url(settings.database_url).get_backend_name()
    try:
        compounds, genetic = metadata_service.count_records(db)
        database = DatabaseStatus(
            status="ok", dialect=dialect, compound_count=compounds, genetic_perturbation_count=genetic
        )
    except DatabaseUnavailableError as exc:
        database = DatabaseStatus(status="unavailable", dialect=dialect, message=exc.message)

    return HealthResponse(
        status="ok" if database.status == "ok" else "degraded",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database=database,
        datasets=store.status(),
    )
