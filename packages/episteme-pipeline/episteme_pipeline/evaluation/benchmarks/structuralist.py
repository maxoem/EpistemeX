"""Adapter for the Structuralist Theory-Net Benchmark (STNB).

This module ingests benchmark JSON-LD graph serializations and maps them into
canonical pipeline domain objects (L1Chunk) and structural NetworkX digraphs /
epistemetrics TheoryGraph instances for intrinsic and extrinsic graph evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

import epistemetrics as em
from episteme_pipeline.contracts.domain import L1Chunk


def _as_list(value: Any) -> list[str]:
    """Normalize a scalar or list JSON-LD value into a list of strings.

    Parameters
    ----------
    value : Any
        A single string identifier, a list of identifiers, or None.

    Returns
    -------
    list of str
        Normalized list of string identifiers.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    if isinstance(value, str):
        return [value]
    return [str(value)]


def load_structuralist_benchmark(
    benchmark_path: str | Path,
) -> tuple[list[L1Chunk], nx.DiGraph]:
    """Load an STNB JSON-LD benchmark file into pipeline chunks and a gold DiGraph.

    Parameters
    ----------
    benchmark_path : str or Path
        Filesystem path to the STNB JSON-LD file.

    Returns
    -------
    tuple of (list of L1Chunk, nx.DiGraph)
        A 2-tuple containing:
        - chunks : list of L1Chunk
            Source text chunks extracted from text anchor annotations in the
            benchmark graph, ordered by sequential appearance.
        - gold_graph : nx.DiGraph
            Directed graph containing formal structuralist nodes and relational edges
            with dual edge attributes ('label' and 'relation').

    Raises
    ------
    FileNotFoundError
        If the specified `benchmark_path` does not exist.
    ValueError
        If the file content is not valid JSON or lacks an `@graph` array.
    """
    path = Path(benchmark_path)
    if not path.is_file():
        raise FileNotFoundError(f"Benchmark file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    graph_nodes = data.get("@graph")
    if not isinstance(graph_nodes, list):
        raise ValueError(f"STNB benchmark file {path} missing '@graph' list.")

    gold_graph = nx.DiGraph()
    chunks: list[L1Chunk] = []
    seen_chunk_ids: set[str] = set()

    for item in graph_nodes:
        node_id = item.get("@id")
        if not node_id:
            continue

        node_type = item.get("@type", "TheoryElement")
        label = item.get("rdfs:label", node_id)
        formal_axiom = (
            item.get("str:formalAxiom")
            or item.get("formalAxiom")
            or item.get("formal_axiom")
            or ""
        )

        # 3. Resilient text anchor resolution across namespaces
        anchor = (
            item.get("Episteme:textAnchor")
            or item.get("glp:textAnchor")
            or item.get("textAnchor")
        )

        if anchor and isinstance(anchor, dict):
            chunk_id = (
                anchor.get("chunkId")
                or anchor.get("chunk_id")
                or f"chunk_{node_id}"
            )
            quote = (
                anchor.get("verbatimQuote")
                or anchor.get("quote")
                or ""
            )
            source_doc_id = (
                anchor.get("sourceDocId")
                or anchor.get("source_doc_id")
                or "unknown_doc"
            )
            char_start = (
                anchor.get("charStart")
                if anchor.get("charStart") is not None
                else anchor.get("char_start")
            )
            char_end = (
                anchor.get("charEnd")
                if anchor.get("charEnd") is not None
                else anchor.get("char_end")
            )

            if chunk_id not in seen_chunk_ids and quote:
                seen_chunk_ids.add(chunk_id)
                chunks.append(
                    L1Chunk(
                        id=chunk_id,
                        text=quote,
                        source_doc_id=source_doc_id,
                        sequence_index=len(chunks),
                        token_count=len(quote.split()),
                        metadata={
                            "char_start": char_start,
                            "char_end": char_end,
                            "anchored_node_id": node_id,
                        },
                    )
                )

        gold_graph.add_node(
            node_id,
            label=label,
            name=label,
            node_type=node_type,
            formal_axiom=formal_axiom,
            anchor=anchor,
            attributes={
                "formalAxiom": formal_axiom,
                "formal_axiom": formal_axiom,
                "textAnchor": anchor,
                "node_type": node_type,
                "label": label,
                "name": label,
            },
        )

    # Second pass for edges: ensures all nodes are registered in the graph
    for item in graph_nodes:
        node_id = item.get("@id")
        if not node_id:
            continue

        # 5. Specialization Poset Orientation (T_0 -> T_1)
        # When sub-theory declares specializes: parent_core, edge flows parent_core -> sub-theory
        spec_targets = _as_list(item.get("str:specializes") or item.get("specializes"))
        for target in spec_targets:
            gold_graph.add_edge(
                target,
                node_id,
                label="specializes",
                relation="specializes",
                weight=1.0,
            )

        spec_by_targets = _as_list(
            item.get("str:specializedBy")
            or item.get("specializedBy")
            or item.get("str:hasSpecialization")
            or item.get("hasSpecialization")
        )
        for target in spec_by_targets:
            gold_graph.add_edge(
                node_id,
                target,
                label="specializes",
                relation="specializes",
                weight=1.0,
            )

        # 4. Complete Edge Coverage: other structuralist relation types
        standard_directed_relations = [
            ("reducesTo", "reducesTo"),
            ("hasConstraint", "hasConstraint"),
            ("hasActualModel", "hasActualModel"),
            ("hasPotentialModel", "hasPotentialModel"),
            ("hasPartialPotentialModel", "hasPartialPotentialModel"),
            ("hasParadigm", "hasParadigm"),
            ("hasIntendedApplication", "hasIntendedApplication"),
            ("presupposes", "presupposes"),
        ]

        for rel_key, rel_label in standard_directed_relations:
            val = item.get(f"str:{rel_key}") or item.get(rel_key)
            targets = _as_list(val)
            for target in targets:
                gold_graph.add_edge(
                    node_id,
                    target,
                    label=rel_label,
                    relation=rel_label,
                    weight=1.0,
                )

        # Symmetric equivalence: empiricallyEquivalent
        equiv_targets = _as_list(
            item.get("str:empiricallyEquivalent") or item.get("empiricallyEquivalent")
        )
        for target in equiv_targets:
            gold_graph.add_edge(
                node_id,
                target,
                label="empiricallyEquivalent",
                relation="empiricallyEquivalent",
                weight=1.0,
            )
            gold_graph.add_edge(
                target,
                node_id,
                label="empiricallyEquivalent",
                relation="empiricallyEquivalent",
                weight=1.0,
            )

    return chunks, gold_graph


def structuralist_digraph_to_theory_graph(
    gold_graph: nx.DiGraph,
    name: str = "STNBGoldGraph",
) -> em.TheoryGraph:
    """Convert an STNB NetworkX gold DiGraph to an epistemetrics TheoryGraph.

    Parameters
    ----------
    gold_graph : nx.DiGraph
        Ground-truth directed graph loaded by `load_structuralist_benchmark`.
    name : str, optional
        Name of the created TheoryGraph (default: "STNBGoldGraph").

    Returns
    -------
    em.TheoryGraph
        Populated TheoryGraph container.
    """
    tg = em.TheoryGraph(name=name)

    for nid, data in gold_graph.nodes(data=True):
        node_id = str(nid)
        attrs = dict(data)
        node_type = em.NodeType.from_str(
            attrs.get("node_type", attrs.get("type", attrs.get("label", "concept")))
        )
        epistemic_status = em.EpistemicStatus.HARD_CORE if node_type in {
            em.NodeType.ACTUAL_MODEL,
            em.NodeType.AXIOM,
        } else em.EpistemicStatus.NEUTRAL

        tg.add_node(
            node_id=node_id,
            name=str(attrs.get("name", attrs.get("label", node_id))),
            node_type=node_type,
            epistemic_status=epistemic_status,
            confidence=float(attrs.get("confidence", 1.0)),
            description=attrs.get("description", attrs.get("label")),
            provenance=[attrs["anchor"]["chunkId"]] if attrs.get("anchor") and isinstance(attrs["anchor"], dict) and "chunkId" in attrs["anchor"] else [],
            attributes=attrs,
        )

    for u, v, data in gold_graph.edges(data=True):
        rel_str = str(data.get("relation", data.get("label", "explains")))
        rel_type = em.RelationType.from_str(rel_str)
        tg.add_edge(
            source=str(u),
            target=str(v),
            relation_type=rel_type,
            confidence=float(data.get("confidence", 1.0)),
            weight=float(data.get("weight", 1.0)),
            attributes=dict(data),
        )

    return tg


def load_structuralist_theory_graph(
    benchmark_path: str | Path,
    name: str = "STNBGoldGraph",
) -> tuple[list[L1Chunk], em.TheoryGraph]:
    """Load an STNB benchmark file directly into pipeline chunks and an epistemetrics TheoryGraph.

    Parameters
    ----------
    benchmark_path : str or Path
        Filesystem path to the STNB JSON-LD file.
    name : str, optional
        Name of the created TheoryGraph (default: "STNBGoldGraph").

    Returns
    -------
    tuple of (list of L1Chunk, em.TheoryGraph)
        Loaded L1 chunks and TheoryGraph.
    """
    chunks, nx_graph = load_structuralist_benchmark(benchmark_path)
    tg = structuralist_digraph_to_theory_graph(nx_graph, name=name)
    return chunks, tg
