from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from episteme_pipeline.protocols.fingerprint import Fingerprintable


class DataSourceAdapter(Fingerprintable, ABC):
    """
    Converts a raw source file into clean Markdown text ready for chunking.

    Register adapters in Phase1Runner(adapters=...) (ordered by priority).
    The first adapter whose can_handle() returns True is used.

    Built-in adapters (pipeline/phases/phase1_foundation/adapters/):
      - TexAdapter      — .tex files via Pandoc
      - MarkdownAdapter — .md / .markdown files (passthrough + cleanup)
      - PlainTextAdapter — .txt files (passthrough)
    """

    @abstractmethod
    def can_handle(self, path: Path) -> bool: ...

    @abstractmethod
    def convert(self, path: Path, bib_paths: list[Path] | None = None) -> str:
        """
        Returns clean Markdown text.
        bib_paths: optional bibliography files (used by TexAdapter for citations).
        """
        ...

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic fingerprint representation of the adapter.

        Returns
        -------
        dict[str, Any]
            Deterministic component configuration dictionary.
        """
        return {"type": self.__class__.__name__}
