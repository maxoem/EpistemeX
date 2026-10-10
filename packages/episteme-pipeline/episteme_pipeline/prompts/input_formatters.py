"""Input formatters for structuring contexts injected into LLM prompts.

Provides decoupled serialization strategies (JSON, YAML, Text) using the Strategy pattern
to maximize model comprehension of structural contexts (e.g., subgraphs, memory).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from episteme_pipeline.contracts.domain import SubGraph


class InputFormatStrategy(str, Enum):
    JSON = "json"
    YAML = "yaml"
    TEXT = "text"


class BaseSubgraphFormatter(ABC):
    """Abstract strategy interface for formatting subgraph envelopes."""

    @abstractmethod
    def format(
        self, 
        env_a: "SubGraph", 
        env_b: "SubGraph", 
        include_description: bool = True
    ) -> str:
        """Render two subgraph envelopes as a formatted string."""
        ...

    @staticmethod
    def _extract_payload(
        env_a: "SubGraph", 
        env_b: "SubGraph", 
        include_description: bool = True
    ) -> dict[str, Any]:
        """Extract merged node and edge dictionaries from subgraph envelopes."""
        all_nodes = {n.id: n for n in env_a.nodes + env_b.nodes}
        all_triples = env_a.triples + env_b.triples

        nodes_data = []
        for n in sorted(all_nodes.values(), key=lambda x: x.id):
            node_dict = {"id": n.id, "label": n.label, "name": n.name}
            if include_description and n.description:
                node_dict["description"] = n.description
            nodes_data.append(node_dict)

        edges_data = []
        for t in all_triples:
            edges_data.append({
                "subject": t.subject_id,
                "predicate": t.predicate,
                "object": t.object_id,
            })

        payload: dict[str, Any] = {"nodes": nodes_data, "edges": edges_data}
        if not payload["nodes"] and not payload["edges"]:
            payload = {"message": "No graph context available."}
        return payload


class JsonSubgraphFormatter(BaseSubgraphFormatter):
    """JSON serialization strategy (Recommended for LLM understanding)."""

    def format(
        self, 
        env_a: "SubGraph", 
        env_b: "SubGraph", 
        include_description: bool = True
    ) -> str:
        payload = self._extract_payload(env_a, env_b, include_description)
        return json.dumps(payload, indent=2, ensure_ascii=False)


class YamlSubgraphFormatter(BaseSubgraphFormatter):
    """YAML serialization strategy."""

    def format(
        self, 
        env_a: "SubGraph", 
        env_b: "SubGraph", 
        include_description: bool = True
    ) -> str:
        payload = self._extract_payload(env_a, env_b, include_description)
        try:
            import yaml
            return yaml.dump(payload, default_flow_style=False, allow_unicode=True)
        except ImportError:
            return json.dumps(payload, indent=2, ensure_ascii=False)


class TextSubgraphFormatter(BaseSubgraphFormatter):
    """Plain-text string rendering strategy."""

    def format(
        self, 
        env_a: "SubGraph", 
        env_b: "SubGraph", 
        include_description: bool = True
    ) -> str:
        lines: list[str] = []

        all_nodes = {n.id: n for n in env_a.nodes + env_b.nodes}
        for n in sorted(all_nodes.values(), key=lambda x: x.id):
            if include_description:
                desc = f": {n.description}" if n.description else ""
                lines.append(f"  [{n.label}] {n.name}{desc}")
            else:
                lines.append(f"  [{n.label}] {n.name}")

        all_triples = env_a.triples + env_b.triples
        for t in all_triples:
            lines.append(f"  ({t.subject_id})-[{t.predicate}]->({t.object_id})")

        return "\n".join(lines) if lines else "No graph context available."


# Strategy Registry
_FORMATTERS: Dict[InputFormatStrategy, BaseSubgraphFormatter] = {
    InputFormatStrategy.JSON: JsonSubgraphFormatter(),
    InputFormatStrategy.YAML: YamlSubgraphFormatter(),
    InputFormatStrategy.TEXT: TextSubgraphFormatter(),
}


def format_subgraph_envelope(
    env_a: "SubGraph", 
    env_b: "SubGraph", 
    strategy: InputFormatStrategy = InputFormatStrategy.JSON, 
    include_description: bool = True
) -> str:
    """Render subgraph envelopes using the configured strategy."""
    formatter = _FORMATTERS.get(strategy, _FORMATTERS[InputFormatStrategy.JSON])
    return formatter.format(env_a, env_b, include_description=include_description)
