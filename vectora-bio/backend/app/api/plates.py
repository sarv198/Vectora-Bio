"""Plate layouts of the imported screen (which perturbation sits in which well)."""

from fastapi import APIRouter

from app.api.deps import StoreDep
from app.schemas.common import DATA_ERROR_RESPONSES
from app.schemas.profile import PlateLayout, PlateSummary
from app.services import profile_service

router = APIRouter(responses=DATA_ERROR_RESPONSES)


@router.get("", response_model=list[PlateSummary], summary="Imaged plates with modality and well counts")
def list_plates(store: StoreDep) -> list[PlateSummary]:
    return profile_service.list_plates(store)


@router.get("/{plate}", response_model=PlateLayout, summary="Every imaged well of one plate")
def plate_layout(plate: str, store: StoreDep) -> PlateLayout:
    return profile_service.plate_layout(store, plate)
