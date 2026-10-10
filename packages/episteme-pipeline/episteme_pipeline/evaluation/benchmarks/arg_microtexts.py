"""Adapter for the Arg-Microtexts argumentation benchmark.

Maps argumentative claims, premises, and stance relations to pipeline
domain objects (TheoryAtom, TheoryRelation).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from episteme_pipeline.contracts.domain import TheoryAtom, TheoryRelation


def load_arg_microtexts_subset(
    path: str | Path,
    limit: int = 5,
) -> dict[str, Any]:
    """Load and map a subset of the Arg-Microtexts dataset to pipeline domain objects.

    Parameters
    ----------
    path : str or Path
        Path to the Arg-Microtexts JSON file.
    limit : int, optional
        Maximum number of microtexts to load (default: 5).

    Returns
    -------
    dict[str, Any]
        Dictionary containing metadata, L3 theory atoms, and L3 relations.
    """
    file_path = Path(path)
    atoms: list[TheoryAtom] = []
    relations: list[TheoryRelation] = []

    if not file_path.exists():
        return {
            "metadata": {"dataset_type": "arg_microtexts", "limit": limit, "error": f"File not found: {path}"},
            "l2_entities": [],
            "l2_triples": [],
            "l3_atoms": [],
            "l3_relations": [],
        }

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for i, doc in enumerate(data[:limit]):
            doc_id = doc.get("id", f"doc_{i}")
            components = doc.get("components", [])
            rels = doc.get("relations", [])

            for comp in components:
                atom = TheoryAtom(
                    id=comp["id"],
                    text=comp["text"],
                    component_type=comp.get("type", "CLAIM"),
                    confidence=1.0,
                    source_chunk_id=comp.get("chunk_id", f"chunk_{doc_id}"),
                )
                atoms.append(atom)

            for rel in rels:
                relation = TheoryRelation(
                    source_id=rel["source_id"],
                    target_id=rel["target_id"],
                    relation_type=rel.get("type", "SUPPORTS"),
                    confidence=1.0,
                    scope="local",
                )
                relations.append(relation)

    except Exception as e:
        return {
            "metadata": {"dataset_type": "arg_microtexts", "limit": limit, "error": str(e)},
            "l2_entities": [],
            "l2_triples": [],
            "l3_atoms": [],
            "l3_relations": [],
        }

    return {
        "metadata": {"dataset_type": "arg_microtexts", "limit": limit},
        "l2_entities": [],
        "l2_triples": [],
        "l3_atoms": atoms,
        "l3_relations": relations,
    }
