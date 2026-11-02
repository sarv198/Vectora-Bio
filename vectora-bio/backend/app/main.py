"""FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import compounds, evaluation, genes, mechanisms, rescue
from app.config import settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.exception_handler(NotImplementedError)
async def not_implemented(_request: Request, exc: NotImplementedError) -> JSONResponse:
    return JSONResponse(status_code=501, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(compounds.router, prefix="/api/compounds", tags=["compounds"])
app.include_router(genes.router, prefix="/api/genes", tags=["genes"])
app.include_router(mechanisms.router, prefix="/api/mechanisms", tags=["mechanisms"])
app.include_router(rescue.router, prefix="/api/rescue", tags=["rescue"])
app.include_router(evaluation.router, prefix="/api/evaluation", tags=["evaluation"])
