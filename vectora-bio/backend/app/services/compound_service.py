"""Compound queries over processed tables."""

from app.schemas.compound import Compound
from app.services.data_loader import load_records


def _compound_from_row(row: dict) -> Compound | None:
    raw_id = row.get("compound_id")
    if raw_id is None:
        raw_id = row.get("id")
    if raw_id is None:
        return None
    name = row.get("name")
    return Compound(
        compound_id=str(raw_id).strip(),
        name="" if name is None else str(name).strip(),
        smiles=None if row.get("smiles") is None else str(row["smiles"]),
        inchikey=None if row.get("inchikey") is None else str(row["inchikey"]),
    )


def list_compounds(query: str | None = None, limit: int = 50) -> list[Compound]:
    compounds: list[Compound] = []
    for row in load_records("compounds"):
        compound = _compound_from_row(row)
        if compound is None or compound.compound_id == "":
            continue
        compounds.append(compound)
    if query:
        needle = query.lower()
        compounds = [
            compound
            for compound in compounds
            if needle in compound.compound_id.lower() or needle in compound.name.lower()
        ]
    return compounds[:limit]


def get_compound(compound_id: str) -> Compound | None:
    for compound in list_compounds(limit=10**9):
        if compound.compound_id == compound_id:
            return compound
    return None
