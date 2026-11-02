"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api import compounds, evaluation, genes, health, moa, rescue, similarity, targets
from app.config import get_settings
from app.db.session import init_db, safe_database_url
from app.errors import register_exception_handlers

logger = logging.getLogger("vectora")

DESCRIPTION = """
Analysis of high-dimensional cellular phenotypic profiles (e.g. JUMP Cell Painting)
from chemical and genetic perturbations.

Endpoints that depend on data that has not been imported return **503** with
`error = "data_not_loaded"` and the list of missing datasets. No endpoint returns
placeholder or fabricated predictions.
"""

TAGS = [
    {"name": "health", "description": "Service, database, and dataset status."},
    {"name": "compounds", "description": "Imported compound metadata."},
    {"name": "genes", "description": "Imported genetic perturbation metadata."},
    {"name": "similarity", "description": "Compound-to-compound phenotypic similarity."},
    {"name": "targets", "description": "Compound-to-gene matching and target prioritization."},
    {"name": "moa", "description": "Similarity-based mechanism-of-action inference."},
    {"name": "rescue", "description": "Phenotypic rescue / perturbation reversal."},
    {"name": "evaluation", "description": "Recorded evaluation metrics."},
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    if settings.auto_create_tables:
        try:
            init_db()
        except SQLAlchemyError as exc:
            logger.warning(
                "Database %s is not reachable (%s). The API will start; database-backed endpoints return 503.",
                safe_database_url(),
                exc.__class__.__name__,
            )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(compounds.router, prefix="/api/compounds", tags=["compounds"])
    app.include_router(genes.router, prefix="/api/genes", tags=["genes"])
    app.include_router(similarity.router, prefix="/api/similarity", tags=["similarity"])
    app.include_router(targets.router, prefix="/api/targets", tags=["targets"])
    app.include_router(moa.router, prefix="/api/moa", tags=["moa"])
    app.include_router(rescue.router, prefix="/api/rescue", tags=["rescue"])
    app.include_router(evaluation.router, prefix="/api/evaluation", tags=["evaluation"])
    return app


app = create_app()
