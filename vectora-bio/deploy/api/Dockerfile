# CellScope API image, run on Render as an image-backed web service.
#
# Build context is the folder made by scripts/stage_api.py:
#   backend/           FastAPI app (no venv, tests or caches)
#   data/processed/    consensus profiles and well tables (about 27 MB)
# Secrets (DATABASE_URL) and CORS_ORIGINS are set in the host's environment settings, never here.

FROM python:3.11-slim

RUN useradd -m -u 1000 user

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY --chown=user backend backend
COPY --chown=user data/processed data/processed

USER user

# Public-deployment defaults; each can be overridden in the host's environment variables.
#   DATA_RAW_DIR      cell images are cached here on first view; /tmp is writable and is
#                     cleared when the service restarts (images are simply fetched again).
#   PERSIST_ANALYSIS_RUNS=false   do not log every visitor's query to the database.
#   EVALUATION_RUNS_ENABLED=false hide "Run benchmarks"; stored results stay viewable.
#   MALLOC_ARENA_MAX=2            stop each worker thread keeping its own pool of freed
#                                 memory (matters on a 512 MB instance).
#   CELL_IMAGE_CACHE_MB=256       downloaded microscopy files kept on disk (least recently
#                                 used removed beyond this); without it they grow ~28 MB a visit.
#   CELL_IMAGE_RENDER_CACHE / CELL_IMAGE_TILE_CACHE  rendered images kept in memory.
#   REQUEST_THREADS=8             requests processed at once; the rest queue, so a burst on
#                                 the slow free CPU cannot pile up memory.
ENV DATA_PROCESSED_DIR=/app/data/processed \
    DATA_RAW_DIR=/tmp/cellscope-raw \
    ENVIRONMENT=production \
    PERSIST_ANALYSIS_RUNS=false \
    EVALUATION_RUNS_ENABLED=false \
    PYTHONUNBUFFERED=1 \
    MALLOC_ARENA_MAX=2 \
    CELL_IMAGE_CACHE_MB=256 \
    CELL_IMAGE_RENDER_CACHE=40 \
    CELL_IMAGE_TILE_CACHE=96 \
    REQUEST_THREADS=8

WORKDIR /app/backend
# Render sets PORT (10000 by default).
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips '*'"]
