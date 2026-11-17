"""Raw Cell Painting microscopy fields, fetched on demand and rendered as PNG."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.api.deps import StoreDep
from app.data.cell_images import DEFAULT_FIELD, CellImageSource, get_cell_image_source
from app.data.profile_store import ProfileStore
from app.errors import NotFoundError
from app.schemas.common import DATA_ERROR_RESPONSES, ProfileType

router = APIRouter(responses=DATA_ERROR_RESPONSES)
ImagesDep = Annotated[CellImageSource, Depends(get_cell_image_source)]


def _known_plates(store: ProfileStore) -> set[str]:
    plates: set[str] = set()
    for profile_type in ProfileType:
        wells = store.wells(profile_type)
        if wells is not None and "Metadata_Plate" in wells.columns:
            plates.update(wells["Metadata_Plate"].astype(str).unique())
    return plates


@router.get(
    "/{plate}/{well}",
    summary="One microscopy field as PNG (channels blended, or one channel in grayscale)",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def well_image(
    plate: str,
    well: str,
    images: ImagesDep,
    store: StoreDep,
    field: int = Query(default=DEFAULT_FIELD, ge=1, le=9, description="Field of view (site) within the well."),
    channels: str = Query(default="DNA,ER,Mito", description="Comma-separated: DNA, ER, RNA, AGP, Mito, Brightfield."),
    size: int = Query(default=540, description="Output edge length in px: 270, 360, 540 or 1080."),
    ref: str | None = Query(default=None, description="Same-plate well that sets the display range."),
    grayscale: bool = False,
) -> Response:
    # Only plates of the imported dataset can be requested (no arbitrary remote fetches).
    if plate not in _known_plates(store):
        raise NotFoundError(f"Plate {plate!r} is not part of the imported dataset.")
    png = images.render(
        plate,
        well,
        field,
        [c.strip() for c in channels.split(",") if c.strip()],
        size=size,
        reference_well=ref,
        grayscale=grayscale,
    )
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=604800"})
