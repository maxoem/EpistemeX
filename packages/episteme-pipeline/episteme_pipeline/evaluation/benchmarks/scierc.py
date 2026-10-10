"""Adapter for the SciERC scientific information extraction benchmark.

Maps SciERC dataset annotations (sentences, NER spans, relation triples) to
Grund GLP pipeline domain objects (L2Entity, L2Triple).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from episteme_pipeline.contracts.domain import L2Entity, L2Triple


def load_scierc_subset(
    path: str | Path,
    limit: int = 5,
) -> dict[str, Any]:
    """Load and map a subset of the SciERC dataset to pipeline domain objects.

    Parameters
    ----------
    path : str or Path
        Path to the JSON / JSONL SciERC file.
    limit : int, optional
        Maximum number of document entries to load (default: 5).

    Returns
    -------
    dict[str, Any]
        Dictionary containing metadata, L2 entities, and L2 triples.
    """
    file_path = Path(path)
    entities: list[L2Entity] = []
    triples: list[L2Triple] = []

    if not file_path.exists():
        return {
            "metadata": {"dataset_type": "scierc", "limit": limit, "error": f"File not found: {path}"},
            "l2_entities": [],
            "l2_triples": [],
            "l3_atoms": [],
            "l3_relations": [],
        }

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for i, line in enumerate(lines[:limit]):
            if not line.strip():
                continue
            data = json.loads(line)
            doc_id = data.get("doc_key", f"doc_{i}")
            sentences = data.get("sentences", [])
            ner = data.get("ner", [])
            relations = data.get("relations", [])

            # Flatten tokens for word-level indexing
            tokens = [token for sentence in sentences for token in sentence]

            # Map entities
            entity_map: dict[tuple[int, int], L2Entity] = {}
            for ner_list in ner:
                for span in ner_list:
                    start, end, label = span
                    text = " ".join(tokens[start : end + 1])
                    ent_id = f"{doc_id}_ent_{start}_{end}"
                    entity = L2Entity(
                        id=ent_id,
                        name=text,
                        label=label,
                        description="",
                        is_mature=True,
                    )
                    entities.append(entity)
                    entity_map[(start, end)] = entity

            # Map relations
            for rel_list in relations:
                for rel in rel_list:
                    start1, end1, start2, end2, rel_type = rel
                    head_ent = entity_map.get((start1, end1))
                    tail_ent = entity_map.get((start2, end2))

                    if head_ent and tail_ent:
                        triple = L2Triple(
                            subject_id=head_ent.id,
                            predicate=rel_type,
                            object_id=tail_ent.id,
                            confidence=1.0,
                            scope="local",
                        )
                        triples.append(triple)

    except Exception as e:
        return {
            "metadata": {"dataset_type": "scierc", "limit": limit, "error": str(e)},
            "l2_entities": [],
            "l2_triples": [],
            "l3_atoms": [],
            "l3_relations": [],
        }

    return {
        "metadata": {"dataset_type": "scierc", "limit": limit},
        "l2_entities": entities,
        "l2_triples": triples,
        "l3_atoms": [],
        "l3_relations": [],
    }
