"""Per-perturbation phenotype summaries (for visual inspection in the UI)."""

from fastapi import APIRouter, Query

from app.api.deps import SettingsDep, StoreDep
from app.schemas.common import DATA_ERROR_RESPONSES, ProfileType
from app.schemas.profile import ProfileComparison, ProfileOverview
from app.services import profile_service

router = APIRouter(responses=DATA_ERROR_RESPONSES)


@router.get(
    "/compare",
    response_model=ProfileComparison,
    summary="Agreement between two perturbations, overall and per compartment x stain channel",
)
def compare(
    store: StoreDep,
    first_type: ProfileType,
    first_id: str,
    second_type: ProfileType,
    second_id: str,
    subtract_controls: bool = Query(default=False, description="Subtract matched control consensus first."),
) -> ProfileComparison:
    return profile_service.compare_profiles(
        store, (first_type, first_id), (second_type, second_id), subtract_controls=subtract_controls
    )


@router.get(
    "/{profile_type}/{perturbation_id}",
    response_model=ProfileOverview,
    summary="Phenotype map, strongest feature changes, response strength and image wells",
)
def overview(
    profile_type: ProfileType, perturbation_id: str, store: StoreDep, settings: SettingsDep
) -> ProfileOverview:
    return profile_service.profile_overview(store, settings, profile_type, perturbation_id)
