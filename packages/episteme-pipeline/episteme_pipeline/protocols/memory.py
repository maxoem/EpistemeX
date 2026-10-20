"""
Protocols and contracts for Episodic Working Memory (Short-Term Memory).

Defines the abstract state interface, GlobalStructuralAnchor data structures,
and eviction signal contracts for stateful context tracking across
sequential chunk extraction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class EvictionSignal:
    """
    Signal produced when a boundary condition is triggered.

    Attributes
    ----------
    boundary_detected : bool
        Whether an episodic boundary was crossed.
    boundary_type : str
        Type of boundary ('structural', 'semantic', or 'none').
    transitional_summary : str | None, optional
        Short 1-2 sentence context bridge summarizing episode closure.
    """

    boundary_detected: bool = False
    boundary_type: str = "none"
    transitional_summary: str | None = None


class WorkingMemoryState(ABC):
    """
    Abstract state interface for Episodic Working Memory.

    Decouples underlying state representations (JSON patches, Pydantic objects,
    key-value dicts) from extraction pipeline orchestration.
    """

    @abstractmethod
    def update(self, state_delta: dict[str, Any]) -> None:
        """
        Update working memory state with variables extracted from chunk $C_i$.

        Parameters
        ----------
        state_delta : dict[str, Any]
            State variable updates (active_entities, unresolved_references, etc.).
        """
        ...

    @abstractmethod
    def reset(self, transitional_summary: str | None = None) -> None:
        """
        Purge short-lived variables from RAM upon episodic eviction boundary.

        Parameters
        ----------
        transitional_summary : str | None, optional
            Optional transitional context bridge to retain for the next episode.
        """
        ...

    @abstractmethod
    def to_prompt_context(self) -> str:
        """
        Format current short-term state variables for prompt injection.

        Returns
        -------
        str
            Formatted prompt context string.
        """
        ...

    @abstractmethod
    def get_raw_state(self) -> dict[str, Any]:
        """
        Return the raw state variables as a dictionary.

        Returns
        -------
        dict[str, Any]
            Dictionary of active state variables.
        """
        ...

    @abstractmethod
    def load_raw_state(self, state: dict[str, Any]) -> None:
        """
        Restore working memory state variables from a raw snapshot dictionary.

        Parameters
        ----------
        state : dict[str, Any]
            State dictionary to restore.
        """
        ...