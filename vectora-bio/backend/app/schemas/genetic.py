"""Genetic perturbation models."""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import GeneticPerturbationType


class GeneticPerturbation(BaseModel):
    """A single genetic reagent (guide, ORF construct, siRNA) targeting one gene."""

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True, coerce_numbers_to_str=True)

    perturbation_id: str = Field(min_length=1, max_length=128)
    gene_id: str = Field(min_length=1, max_length=64, description="Stable gene identifier, e.g. NCBI Gene ID.")
    gene_symbol: str = Field(min_length=1, max_length=64)
    perturbation_type: GeneticPerturbationType
    cell_line: str = Field(min_length=1, max_length=128)
    timepoint: float = Field(gt=0, description="Hours after perturbation.")


class GeneDetail(BaseModel):
    gene_id: str
    gene_symbol: str
    perturbations: list[GeneticPerturbation]
