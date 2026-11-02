"""Engine, session factory, and schema creation."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    if settings.is_sqlite:
        connect_args: dict = {"check_same_thread": False}
    else:
        connect_args = {"connect_timeout": settings.database_connect_timeout_s}
    return create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def safe_database_url() -> str:
    """The configured URL with the password masked, for logs and CLI output."""
    return make_url(get_settings().database_url).render_as_string(hide_password=True)


def init_db() -> None:
    """Create any missing tables. Existing tables are left unchanged."""
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
