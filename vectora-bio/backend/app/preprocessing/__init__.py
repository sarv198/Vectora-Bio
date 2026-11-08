"""Phase 1 preprocessing: raw well-level plate profiles -> normalized, feature-selected consensus profiles.

Steps (see ``build.build_dataset``):
    select plates -> separate compounds / genetic / controls -> normalize to matched controls per plate
    -> select features jointly across modalities -> aggregate replicates -> write Parquet + manifest
"""
