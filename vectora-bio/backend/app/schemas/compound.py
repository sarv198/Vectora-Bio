"""Compound request and response models."""

from pydantic import BaseModel, ConfigDict


class Compound(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    compound_id: str
    name: str
    smiles: str | None = None
    inchikey: str | None = None
