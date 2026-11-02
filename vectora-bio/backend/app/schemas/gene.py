"""Gene response models."""

from pydantic import BaseModel, ConfigDict


class Gene(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    entrez_id: int | None = None
    name: str | None = None
