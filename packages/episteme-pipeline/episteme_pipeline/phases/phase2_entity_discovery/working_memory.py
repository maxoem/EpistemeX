"""
Episodic Working Memory implementations for Phase 2 Entity Discovery.

Provides concrete state machine implementations (JsonPatch, Pydantic, KeyValue),
an EpisodicEvictionHandler for structural and semantic boundary detection, and
the EpisodicWorkingMemoryManager for sequential chunk context propagation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from episteme_pipeline.contracts.domain import GlobalStructuralAnchor, L1Chunk
from episteme_pipeline.protocols.memory import EvictionSignal, WorkingMemoryState

logger = logging.getLogger(__name__)


class WorkingMemorySchema(BaseModel):
    """
    Structured Pydantic schema for Short-Term Memory state variables.

    Attributes
    ----------
    active_entities : list[str]
        List of concepts, entities, or key terms currently under active discussion.
    unresolved_references : list[str]
        Open pronouns, demonstratives, or unanchored claims awaiting resolution.
    current_argument_branch : str | None
        The primary premise or logical argument currently being built.
    transitional_summary : str | None
        Short summary bridge from the previous episode closure, if any.
    """

    active_entities: list[str] = Field(default_factory=list)
    unresolved_references: list[str] = Field(default_factory=list)
    current_argument_branch: str | None = None
    transitional_summary: str | None = None


class JsonPatchWorkingMemoryState(WorkingMemoryState):
    """
    JSON-formatted state machine implementation of WorkingMemoryState.

    Serializes state updates as explicit JSON state variables.
    """

    def __init__(self, initial_state: dict[str, Any] | None = None) -> None:
        self._state: dict[str, Any] = {
            "active_entities": [],
            "unresolved_references": [],
            "current_argument_branch": None,
            "transitional_summary": None,
        }
        if initial_state:
            self.update(initial_state)

    def update(self, state_delta: dict[str, Any]) -> None:
        """
        Update short-term memory state variables.

        Parameters
        ----------
        state_delta : dict[str, Any]
            State dictionary containing updates for active_entities,
            unresolved_references, or current_argument_branch.
        """
        if not state_delta:
            return

        if "active_entities" in state_delta:
            new_entities = state_delta["active_entities"]
            if isinstance(new_entities, list):
                # Unique list preserving insertion order
                combined = self._state["active_entities"] + new_entities
                seen = set()
                self._state["active_entities"] = [
                    e for e in combined if not (e in seen or seen.add(e))
                ][-15:]  # Bound to last 15 active entities

        if "unresolved_references" in state_delta:
            new_refs = state_delta["unresolved_references"]
            if isinstance(new_refs, list):
                self._state["unresolved_references"] = new_refs[-10:]

        if state_delta.get("current_argument_branch"):
            self._state["current_argument_branch"] = str(state_delta["current_argument_branch"])

        if state_delta.get("transitional_summary"):
            self._state["transitional_summary"] = str(state_delta["transitional_summary"])

    def reset(self, transitional_summary: str | None = None) -> None:
        """
        Purge short-lived variables from RAM upon episodic eviction boundary.

        Parameters
        ----------
        transitional_summary : str | None, optional
            Optional transitional context bridge to retain for the next episode.
        """
        self._state = {
            "active_entities": [],
            "unresolved_references": [],
            "current_argument_branch": None,
            "transitional_summary": transitional_summary,
        }

    def to_prompt_context(self) -> str:
        """
        Format current short-term state variables into a JSON prompt string.

        Returns
        -------
        str
            Formatted JSON prompt string.
        """
        active = {k: v for k, v in self._state.items() if v}
        if not active:
            return "Active Short-Term Memory: None (Initial Episode State)"
        return f"Active Short-Term Memory (RAM Context):\n{json.dumps(active, indent=2)}"

    def get_raw_state(self) -> dict[str, Any]:
        """
        Return raw state dictionary.

        Returns
        -------
        dict[str, Any]
            State dictionary.
        """
        return dict(self._state)


class PydanticWorkingMemoryState(WorkingMemoryState):
    """
    Pydantic-backed state machine implementation of WorkingMemoryState.
    """

    def __init__(self, initial_schema: WorkingMemorySchema | None = None) -> None:
        self._schema = initial_schema or WorkingMemorySchema()

    def update(self, state_delta: dict[str, Any]) -> None:
        """
        Update state variables via Pydantic model updates.

        Parameters
        ----------
        state_delta : dict[str, Any]
            State delta updates.
        """
        if not state_delta:
            return

        current_dict = self._schema.model_dump()
        if "active_entities" in state_delta and isinstance(state_delta["active_entities"], list):
            combined = current_dict["active_entities"] + state_delta["active_entities"]
            seen = set()
            current_dict["active_entities"] = [e for e in combined if not (e in seen or seen.add(e))][-15:]

        if "unresolved_references" in state_delta and isinstance(state_delta["unresolved_references"], list):
            current_dict["unresolved_references"] = state_delta["unresolved_references"][-10:]

        if state_delta.get("current_argument_branch"):
            current_dict["current_argument_branch"] = str(state_delta["current_argument_branch"])

        if state_delta.get("transitional_summary"):
            current_dict["transitional_summary"] = str(state_delta["transitional_summary"])

        self._schema = WorkingMemorySchema(**current_dict)

    def reset(self, transitional_summary: str | None = None) -> None:
        """
        Purge short-lived variables from RAM.

        Parameters
        ----------
        transitional_summary : str | None, optional
            Optional transitional context bridge.
        """
        self._schema = WorkingMemorySchema(transitional_summary=transitional_summary)

    def to_prompt_context(self) -> str:
        """
        Format Pydantic schema into prompt context.

        Returns
        -------
        str
            Formatted prompt text.
        """
        data = self._schema.model_dump(exclude_none=True, exclude_defaults=True)
        if not data:
            return "Active Short-Term Memory: None (Initial Episode State)"
        return f"Active Short-Term Memory (RAM Context):\n{json.dumps(data, indent=2)}"

    def get_raw_state(self) -> dict[str, Any]:
        """
        Return raw state dictionary.

        Returns
        -------
        dict[str, Any]
            State dictionary.
        """
        return self._schema.model_dump()


class KeyValueWorkingMemoryState(WorkingMemoryState):
    """
    Key-Value text formatted state machine implementation of WorkingMemoryState.
    """

    def __init__(self, initial_state: dict[str, Any] | None = None) -> None:
        self._state: dict[str, Any] = initial_state or {}

    def update(self, state_delta: dict[str, Any]) -> None:
        """
        Update key-value state.

        Parameters
        ----------
        state_delta : dict[str, Any]
            Key-value state dictionary.
        """
        self._state.update(state_delta)

    def reset(self, transitional_summary: str | None = None) -> None:
        """
        Reset key-value state.

        Parameters
        ----------
        transitional_summary : str | None, optional
            Optional transitional context bridge.
        """
        self._state = {"transitional_summary": transitional_summary} if transitional_summary else {}

    def to_prompt_context(self) -> str:
        """
        Format key-value state into text.

        Returns
        -------
        str
            Formatted key-value prompt text.
        """
        if not self._state:
            return "Active Short-Term Memory: None (Initial Episode State)"
        lines = ["Active Short-Term Memory (RAM Context):"]
        for k, v in self._state.items():
            if v:
                lines.append(f"- {k}: {v}")
        return "\n".join(lines)

    def get_raw_state(self) -> dict[str, Any]:
        """
        Return raw state dictionary.

        Returns
        -------
        dict[str, Any]
            State dictionary.
        """
        return dict(self._state)


class EpisodicEvictionHandler:
    """
    Monitors structural and semantic boundary signals to trigger episodic eviction resets in RAM.
    """

    def __init__(self) -> None:
        self._last_section_path: str | None = None
        self._last_parent_header: str | None = None

    def evaluate(
        self,
        chunk: L1Chunk,
        semantic_boundary_detected: bool = False,
        transitional_summary: str | None = None,
    ) -> EvictionSignal:
        """
        Evaluate structural and semantic triggers for a given chunk.

        Parameters
        ----------
        chunk : L1Chunk
            Current document chunk.
        semantic_boundary_detected : bool, optional
            Boolean flag returned by LLM extraction output, by default False.
        transitional_summary : str | None, optional
            Optional summary bridge returned by LLM extraction, by default None.

        Returns
        -------
        EvictionSignal
            Eviction signal containing boundary detection status and type.
        """
        meta = chunk.metadata if isinstance(chunk.metadata, dict) else {}
        section_path = meta.get("section_path") or meta.get("chapter") or chunk.chapter_id
        parent_header = meta.get("parent_header") or meta.get("header")

        structural_boundary = False
        if self._last_section_path is not None and section_path != self._last_section_path or self._last_parent_header is not None and parent_header != self._last_parent_header:
            structural_boundary = True

        # Update last tracked structural coordinates
        self._last_section_path = section_path
        self._last_parent_header = parent_header

        if structural_boundary:
            logger.info("Structural boundary detected at chunk %s", chunk.id)
            return EvictionSignal(
                boundary_detected=True,
                boundary_type="structural",
                transitional_summary=transitional_summary,
            )

        if semantic_boundary_detected:
            logger.info("Semantic LLM boundary detected at chunk %s", chunk.id)
            return EvictionSignal(
                boundary_detected=True,
                boundary_type="semantic",
                transitional_summary=transitional_summary,
            )

        return EvictionSignal(boundary_detected=False, boundary_type="none")


class EpisodicWorkingMemoryManager:
    """
    Orchestrates GlobalStructuralAnchor and WorkingMemoryState during sequential chunk processing.

    Parameters
    ----------
    anchor : GlobalStructuralAnchor | None, optional
        Optional user-provided GlobalStructuralAnchor, by default None.
    state_strategy : str, optional
        Format strategy for working memory state ('json_patch', 'pydantic', 'key_value'),
        by default 'json_patch'.
    """

    def __init__(
        self,
        anchor: GlobalStructuralAnchor | None = None,
        state_strategy: str = "json_patch",
    ) -> None:
        self.anchor = anchor
        self.state_strategy = state_strategy
        self.state = self._create_state_instance(state_strategy)
        self.eviction_handler = EpisodicEvictionHandler()

    def _create_state_instance(self, strategy: str) -> WorkingMemoryState:
        if strategy == "pydantic":
            return PydanticWorkingMemoryState()
        elif strategy == "key_value":
            return KeyValueWorkingMemoryState()
        else:
            return JsonPatchWorkingMemoryState()

    def get_effective_anchor(self, chunk: L1Chunk | None = None) -> GlobalStructuralAnchor | None:
        """
        Return the configured structural anchor, or None if not set.

        Parameters
        ----------
        chunk : L1Chunk | None, optional
            Optional chunk parameter for interface compatibility, by default None.

        Returns
        -------
        GlobalStructuralAnchor | None
            Configured structural anchor, or None if no anchor is active.
        """
        return self.anchor

    def process_step(
        self,
        chunk: L1Chunk,
        state_delta: dict[str, Any] | None,
        semantic_boundary_detected: bool = False,
        transitional_summary: str | None = None,
    ) -> EvictionSignal:
        """
        Apply state delta and evaluate episodic eviction reset.

        Parameters
        ----------
        chunk : L1Chunk
            Current chunk.
        state_delta : dict[str, Any] | None
            State updates extracted from chunk.
        semantic_boundary_detected : bool, optional
            Semantic boundary flag from LLM, by default False.
        transitional_summary : str | None, optional
            Optional transitional summary, by default None.

        Returns
        -------
        EvictionSignal
            Resulting eviction signal.
        """
        if state_delta:
            self.state.update(state_delta)

        signal = self.eviction_handler.evaluate(
            chunk=chunk,
            semantic_boundary_detected=semantic_boundary_detected,
            transitional_summary=transitional_summary,
        )

        if signal.boundary_detected:
            self.state.reset(transitional_summary=signal.transitional_summary)

        return signal
