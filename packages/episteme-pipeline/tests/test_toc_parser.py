"""
Unit and integration tests for the ToC Parser Strategy system (MarkdownToCParser,
LaTeXToCParser, FallbackToCParser, AutoToCParser, and Phase 1 → Phase 2 propagation).
"""

from __future__ import annotations

from pathlib import Path

from episteme_pipeline.contracts.domain import GlobalStructuralAnchor
from episteme_pipeline.phases.phase1_foundation.toc_parser import (
    AutoToCParser,
    FallbackToCParser,
    LaTeXToCParser,
    MarkdownToCParser,
    ToCParserStrategy,
)


def test_markdown_toc_parser() -> None:
    """Test MarkdownToCParser on multi-level header structures."""
    parser = MarkdownToCParser()
    assert parser.can_handle("doc.md", "# Title")
    assert parser.can_handle(None, "# Chapter 1\n## Section 1.1")
    assert not parser.can_handle("doc.txt", "Plain text without headers")

    md_text = """
Preamble text here.

# 1. Introduction
Some intro text.

## 1.1 Background
Background details.

### 1.1.1 Historical Context
Deep context.

# 2. Main Dialectic
Dialectic text.
"""
    anchor = parser.parse(md_text, "Philosophical Treatise")
    assert isinstance(anchor, GlobalStructuralAnchor)
    context_str = anchor.to_prompt_context()

    assert "1. Introduction" in context_str
    assert "- 1.1 Background" in context_str
    assert "- 1.1.1 Historical Context" in context_str
    assert "2. Main Dialectic" in context_str


def test_latex_toc_parser() -> None:
    """Test LaTeXToCParser on LaTeX sectioning commands."""
    parser = LaTeXToCParser()
    assert parser.can_handle("paper.tex", r"\documentclass{article}")
    assert parser.can_handle(None, r"\section{Foundations}")
    assert not parser.can_handle("doc.md", "# Header")

    tex_text = r"""
\documentclass{article}
\begin{document}

\chapter{Critique of Pure Reason}
\section{Transcendental Aesthetic}
\subsection{Space}
\subsection{Time}
\section{Transcendental Logic}

\end{document}
"""
    anchor = parser.parse(tex_text, "Critique")
    context_str = anchor.to_prompt_context()

    assert "Critique of Pure Reason" in context_str
    assert "Transcendental Aesthetic" in context_str
    assert "Space" in context_str
    assert "Time" in context_str
    assert "Transcendental Logic" in context_str


def test_fallback_toc_parser() -> None:
    """Test FallbackToCParser on unformatted plain text."""
    parser = FallbackToCParser()
    assert parser.can_handle("file.raw", "Random unformatted text")

    text = "Line 1: Plain unformatted text without any section headers."
    anchor = parser.parse(text, "Raw Document")
    context_str = anchor.to_prompt_context()

    assert "Raw Document" in context_str
    assert "Line 1: Plain unformatted text" in context_str


def test_auto_toc_parser_dispatcher() -> None:
    """Test AutoToCParser strategy dispatching based on file extension and heuristics."""
    auto = AutoToCParser()

    md_anchor = auto.parse("# MD Section", "MD Doc", path="sample.md")
    assert "MD Section" in md_anchor.to_prompt_context()

    tex_anchor = auto.parse(r"\section{TeX Section}", "TeX Doc", path="sample.tex")
    assert "TeX Section" in tex_anchor.to_prompt_context()

    raw_anchor = auto.parse("Plain text", "Plain Doc", path="sample.xyz")
    assert "Plain Doc" in raw_anchor.to_prompt_context()


class CustomStrategy(ToCParserStrategy):
    """Test custom strategy for dependency injection."""

    def can_handle(self, path: Path | str | None, text: str) -> bool:
        return text.startswith("CUSTOM:")

    def parse(self, text: str, document_title: str) -> GlobalStructuralAnchor:
        return GlobalStructuralAnchor(
            toc_structure=["Custom Structural Anchor"],
            document_summary="Injected Custom Strategy",
        )


def test_auto_toc_parser_custom_strategy_injection() -> None:
    """Test registering a custom strategy in AutoToCParser."""
    auto = AutoToCParser()
    auto.register(CustomStrategy(), prepend=True)

    anchor = auto.parse("CUSTOM: Special Header", "Custom Doc")
    assert "Custom Structural Anchor" in anchor.to_prompt_context()
    assert "Injected Custom Strategy" in anchor.to_prompt_context()
