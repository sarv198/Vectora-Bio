"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.data.profile_store import ProfileStore, get_profile_store
from app.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
StoreDep = Annotated[ProfileStore, Depends(get_profile_store)]
