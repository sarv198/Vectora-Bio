"""Compound models."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Compound(BaseModel):
    """A compound measured in one cell line at one timepoint."""

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True, coerce_numbers_to_str=True)

    compound_id: str = Field(min_length=1, max_length=128, description="Stable identifier, e.g. a JUMP JCP2022 id.")
    compound_name: str = Field(min_length=1, max_length=512)
    moa: str | None = Field(
        default=None,
        max_length=1024,
        description="Annotated mechanism(s) of action. Multiple labels are separated by '|'.",
    )
    known_target: str | None = Field(
        default=None,
        max_length=2048,
        description="Annotated target gene symbol(s). Multiple targets are separated by '|'.",
    )
    cell_line: str = Field(min_length=1, max_length=128)
    timepoint: float = Field(gt=0, description="Hours after perturbation.")
    replicate_count: int = Field(ge=0, description="Number of replicate profiles in the imported dataset.")

    @field_validator("moa", "known_target", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class CompoundDetail(BaseModel):
    """A compound with every (cell line, timepoint) context it was imported for."""

    compound_id: str
    compound_name: str
    moa: str | None = None
    known_target: str | None = None
    contexts: list[Compound]
