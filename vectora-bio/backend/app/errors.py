"""Application errors and their HTTP mapping.

Every error is rendered as ``{"error": <code>, "message": <text>, "details": {...}}``
so the frontend can show an informative state instead of a generic failure.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class VectoraError(Exception):
    status_code = 500
    error_code = "internal_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DataNotLoadedError(VectoraError):
    """A dataset the request depends on has not been imported yet."""

    status_code = 503
    error_code = "data_not_loaded"

    def __init__(self, datasets: list[str], message: str | None = None, hint: str | None = None) -> None:
        names = ", ".join(datasets)
        super().__init__(
            message or f"Required data has not been loaded: {names}.",
            details={"missing_datasets": datasets, "hint": hint or _IMPORT_HINT},
        )
        self.datasets = datasets


class DatabaseUnavailableError(VectoraError):
    status_code = 503
    error_code = "database_unavailable"


class NotFoundError(VectoraError):
    status_code = 404
    error_code = "not_found"


class InvalidQueryError(VectoraError):
    """The request is well-formed but cannot be answered as posed (e.g. ambiguous context)."""

    status_code = 400
    error_code = "invalid_query"


class FeatureMismatchError(VectoraError):
    status_code = 409
    error_code = "feature_mismatch"


class ProfileValidationError(VectoraError):
    status_code = 422
    error_code = "profile_validation_failed"


_IMPORT_HINT = (
    "Import locally downloaded profiles with `python -m app.pipeline.import_profiles` and "
    "metadata with `python -m app.pipeline.import_metadata`. See docs/data_dictionary.md."
)


def _render(exc: VectoraError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "message": exc.message, "details": exc.details},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(VectoraError)
    async def handle_vectora_error(_request: Request, exc: VectoraError) -> JSONResponse:
        return _render(exc)

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "An unexpected error occurred.", "details": {}},
        )
