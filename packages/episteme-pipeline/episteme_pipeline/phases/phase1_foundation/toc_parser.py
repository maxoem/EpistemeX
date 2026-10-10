"""
Table of Contents (ToC) Parser Strategy System for Phase 1 Data Foundation.

Provides a pluggable Strategy & Registry architecture (ToCParserStrategy,
MarkdownToCParser, LaTeXToCParser, FallbackToCParser, AutoToCParser) to extract
global structural anchors from incoming documents during Phase 1 ingestion.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from episteme_pipeline.contracts.domain import GlobalStructuralAnchor

# ---------------------------------------------------------------------------
# Protocol / Interface
# ---------------------------------------------------------------------------


class ToCParserStrategy(Protocol):
    """Protocol for Table of Contents parser strategies."""

    def can_handle(self, path: Path | str | None, text: str) -> bool:
        """
        Check whether this strategy can handle the given file path or raw text.

        Parameters
        ----------
        path : Path | str | None
            Optional file path.
        text : str
            Raw document text.

        Returns
        -------
        bool
            True if this strategy can parse the document structure.
        """
        ...

    def parse(self, text: str, document_title: str) -> GlobalStructuralAnchor:
        """
        Parse raw text into a GlobalStructuralAnchor.

        Parameters
        ----------
        text : str
            Raw document text (Markdown, LaTeX, or plain text).
        document_title : str
            Title of the document.

        Returns
        -------
        GlobalStructuralAnchor
            Parsed structural anchor containing ToC outline and summary.
        """
        ...


# ---------------------------------------------------------------------------
# Concrete Strategies
# ---------------------------------------------------------------------------

_MD_HEADER_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)


class MarkdownToCParser(ToCParserStrategy):
    """Parses Markdown header hierarchies (# to ####) into a GlobalStructuralAnchor."""

    def can_handle(self, path: Path | str | None, text: str) -> bool:
        if path:
            p = Path(path)
            if p.suffix.lower() in (".md", ".markdown", ".mdown", ".mkd"):
                return True
        # Text heuristic fallback: contains Markdown headers
        return bool(_MD_HEADER_RE.search(text))

    def parse(self, text: str, document_title: str) -> GlobalStructuralAnchor:
        lines: list[str] = []
        for match in _MD_HEADER_RE.finditer(text):
            level = len(match.group(1))
            header_text = match.group(2).strip()

            indent = "  " * (level - 1)
            bullet = "-" if level > 1 else ""
            prefix = f"{indent}{bullet} ".lstrip() if level > 1 else f"{indent}"
            lines.append(f"{prefix}{header_text}")

        if not lines:
            lines = [f"{document_title} (No section headers detected)"]

        return GlobalStructuralAnchor(
            toc_structure=lines,
            document_summary=f"Markdown Table of Contents for '{document_title}' ({len(lines)} section headers)",
        )


_LATEX_SECTION_RE = re.compile(
    r"\\(part|chapter|section|subsection|subsubsection)\*?\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}",
    re.IGNORECASE,
)

_LATEX_LEVELS = {
    "part": 1,
    "chapter": 1,
    "section": 2,
    "subsection": 3,
    "subsubsection": 4,
}


class LaTeXToCParser(ToCParserStrategy):
    """Parses LaTeX sectioning commands (\\part, \\chapter, \\section, etc.) into a GlobalStructuralAnchor."""

    def can_handle(self, path: Path | str | None, text: str) -> bool:
        if path:
            p = Path(path)
            if p.suffix.lower() in (".tex", ".latex", ".sty"):
                return True
        # Text heuristic fallback: contains LaTeX documentclass or sectioning commands
        return r"\documentclass" in text or bool(_LATEX_SECTION_RE.search(text))

    def parse(self, text: str, document_title: str) -> GlobalStructuralAnchor:
        lines: list[str] = []
        for match in _LATEX_SECTION_RE.finditer(text):
            cmd = match.group(1).lower()
            title = match.group(2).strip()
            level = _LATEX_LEVELS.get(cmd, 2)

            indent = "  " * (level - 1)
            bullet = "-" if level > 1 else ""
            prefix = f"{indent}{bullet} ".lstrip() if level > 1 else f"{indent}"
            lines.append(f"{prefix}{title}")

        if not lines:
            lines = [f"{document_title} (No LaTeX section commands detected)"]

        return GlobalStructuralAnchor(
            toc_structure=lines,
            document_summary=f"LaTeX Table of Contents for '{document_title}' ({len(lines)} section commands)",
        )


class FallbackToCParser(ToCParserStrategy):
    """Fallback strategy for plain unformatted text or unknown file types."""

    def can_handle(self, path: Path | str | None, text: str) -> bool:
        return True

    def parse(self, text: str, document_title: str) -> GlobalStructuralAnchor:
        first_line = text.strip().split("\n")[0][:100] if text.strip() else document_title
        return GlobalStructuralAnchor(
            toc_structure=[f"{document_title}: {first_line}"],
            document_summary=f"Fallback Anchor for '{document_title}'",
        )


# Default strategy registry order
DEFAULT_TOC_PARSERS: list[ToCParserStrategy] = [
    LaTeXToCParser(),
    MarkdownToCParser(),
    FallbackToCParser(),
]

# ---------------------------------------------------------------------------
# Registry / Dispatcher
# ---------------------------------------------------------------------------


class AutoToCParser:
    """
    Registry & Dispatcher for ToC parser strategies.

    Selects the first registered strategy that returns True for can_handle(path, text).
    Allows injecting custom parser strategies at startup.
    """

    def __init__(self, parsers: Sequence[ToCParserStrategy] | None = None) -> None:
        self.parsers: list[ToCParserStrategy] = list(parsers or DEFAULT_TOC_PARSERS)

    def register(self, parser: ToCParserStrategy, prepend: bool = True) -> None:
        """
        Register a new ToCParserStrategy.

        Parameters
        ----------
        parser : ToCParserStrategy
            Strategy instance.
        prepend : bool, optional
            Whether to insert at the beginning of the strategy chain, by default True.
        """
        if prepend:
            self.parsers.insert(0, parser)
        else:
            self.parsers.append(parser)

    def parse(
        self,
        text: str,
        document_title: str,
        path: Path | str | None = None,
    ) -> GlobalStructuralAnchor:
        """
        Dispatch parsing to the first matching strategy.

        Parameters
        ----------
        text : str
            Raw document text.
        document_title : str
            Title of the document.
        path : Path | str | None, optional
            File path, by default None.

        Returns
        -------
        GlobalStructuralAnchor
            Effective GlobalStructuralAnchor for the document.
        """
        for parser in self.parsers:
            if parser.can_handle(path=path, text=text):
                return parser.parse(text=text, document_title=document_title)

        # Safety net (should be caught by FallbackToCParser)
        return FallbackToCParser().parse(text=text, document_title=document_title)
