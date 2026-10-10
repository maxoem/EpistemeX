"""Baseline dataset export and ingestion utilities for human-in-the-loop curation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from episteme_pipeline.contracts.domain import (
    L2Entity,
    L2Triple,
    TheoryAtom,
    TheoryRelation,
)
from episteme_pipeline.protocols.graph_store import GraphReader


async def export_baseline(graph_reader: GraphReader, output_path: str | Path) -> None:
    """Export a completed pipeline run into a JSON file for manual correction.

    Parameters
    ----------
    graph_reader : GraphReader
        Reader instance connected to the populated graph store.
    output_path : str or Path
        File path where the JSON baseline dataset will be written.
    """
    entities = await graph_reader.get_entities()
    triples = await graph_reader.get_all_entity_triples()
    atoms = await graph_reader.get_theory_atoms()
    relations = await graph_reader.get_all_theory_relations()

    data = {
        "metadata": {
            "exported_at": datetime.now(UTC).isoformat(),
            "dataset_type": "baseline",
            "status": "uncorrected",
            "instructions": "Review and correct entries. Change status to 'gold' when done.",
        },
        "l2_entities": [entity.model_dump() for entity in entities],
        "l2_triples": [triple.model_dump() for triple in triples],
        "l3_atoms": [atom.model_dump() for atom in atoms],
        "l3_relations": [relation.model_dump() for relation in relations],
    }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_gold_standard(path: str | Path) -> dict[str, Any]:
    """Load and validate a gold standard dataset from a JSON file.

    Parameters
    ----------
    path : str or Path
        Path to the JSON file containing the dataset.

    Returns
    -------
    dict[str, Any]
        A dictionary containing dataset metadata and validated domain objects.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "metadata": data.get("metadata", {}),
        "l2_entities": [L2Entity.model_validate(e) for e in data.get("l2_entities", [])],
        "l2_triples": [L2Triple.model_validate(t) for t in data.get("l2_triples", [])],
        "l3_atoms": [TheoryAtom.model_validate(a) for a in data.get("l3_atoms", [])],
        "l3_relations": [TheoryRelation.model_validate(r) for r in data.get("l3_relations", [])],
    }
