"""Adapter for the SciFact claim verification benchmark.

Loads queries and ground-truth evidence document IDs for extrinsic
retrieval and question-answering evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_scifact_subset(
    path: str | Path,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Load a subset of the SciFact dataset for extrinsic retrieval evaluation.

    Parameters
    ----------
    path : str or Path
        Path to the SciFact JSON / JSONL claims file.
    limit : int, optional
        Maximum number of queries to load (default: 5).

    Returns
    -------
    list of dict
        List of dictionaries with 'query' and 'gold_ids' keys.
    """
    queries: list[dict[str, Any]] = []
    file_path = Path(path)
    if not file_path.exists():
        return queries

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines[:limit]:
            if not line.strip():
                continue
            data = json.loads(line)
            query = data.get("claim", "")
            gold_ids = []
            for doc_id in data.get("evidence", {}):
                gold_ids.append(str(doc_id))

            queries.append({
                "query": query,
                "gold_ids": set(gold_ids),
            })
    except Exception:
        return []

    return queries
