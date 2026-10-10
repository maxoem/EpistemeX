"""
Tests for Phase 1 document chunker.

Pure functions verifying section parsing, chunk boundary splitting,
sequence monotonicity, overlap tracking, and pluggable token counters.
"""

import pytest
from episteme_pipeline.phases.phase1_foundation.chunker import (
    RawSection,
    chunk_document,
    chunk_section,
    parse_sections,
)


@pytest.fixture(autouse=True)
def mock_offline_encoder(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Ensure hermetic offline execution during unit tests by disabling network encoder fetch.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest monkeypatch fixture.

    Returns
    -------
    None
    """
    monkeypatch.setattr(
        "episteme_pipeline.phases.phase1_foundation.chunker._get_encoder",
        lambda: None,
    )

MARKDOWN_DOC = """\
# Introduction

This is the introduction paragraph with some content about philosophy.
It discusses Kant and his ideas about the nature of knowledge.

## Background

Hegel was a philosopher who disagreed with Kant.
His dialectical method influenced many later thinkers.

# Methodology

We use a graph-based approach to extract knowledge.
"""


def test_parse_sections_finds_h1_and_h2() -> None:
    """
    Verify header extraction captures level-1 and level-2 sections.

    Returns
    -------
    None
    """
    sections = parse_sections(MARKDOWN_DOC)
    titles = [s.title for s in sections]
    assert "Introduction" in titles
    assert "Background" in titles
    assert "Methodology" in titles


def test_parse_sections_assigns_text() -> None:
    """
    Verify section bodies are correctly attributed to section titles.

    Returns
    -------
    None
    """
    sections = parse_sections(MARKDOWN_DOC)
    intro = next(s for s in sections if s.title == "Introduction")
    assert "Kant" in intro.text
    assert "knowledge" in intro.text


def test_parse_sections_returns_raw_sections() -> None:
    """
    Verify returned objects match the RawSection dataclass contract.

    Returns
    -------
    None
    """
    sections = parse_sections(MARKDOWN_DOC)
    assert all(isinstance(s, RawSection) for s in sections)


def test_parse_sections_empty_doc() -> None:
    """
    Verify empty markdown string returns an empty list.

    Returns
    -------
    None
    """
    assert parse_sections("") == []


def test_parse_sections_no_headers() -> None:
    """
    Verify text without headers returns sections without errors.

    Returns
    -------
    None
    """
    text = "Plain text with no headers at all."
    sections = parse_sections(text)
    assert isinstance(sections, list)


def test_chunk_section_single_chunk_for_short_text() -> None:
    """
    Verify text below max_tokens produces a single chunk.

    Returns
    -------
    None
    """
    section = RawSection(
        title="Intro",
        level=1,
        text="Short text.",
    )
    chunks = chunk_section(section, max_tokens=512, overlap_tokens=64)
    assert len(chunks) == 1
    assert "Short text." in chunks[0].text


def test_chunk_section_splits_long_text() -> None:
    """
    Verify paragraphs exceeding max_tokens are split into multiple chunks.

    Returns
    -------
    None
    """
    paragraphs = [" ".join([f"word{j}" for j in range(30)]) for _ in range(10)]
    long_text = "\n\n".join(paragraphs)
    section = RawSection(title="Long", level=1, text=long_text)
    chunks = chunk_section(section, max_tokens=80, overlap_tokens=10)
    assert len(chunks) > 1


def test_chunk_section_overlap_produces_shared_content() -> None:
    """
    Verify overlap window carries trailing tokens from chunk N into N+1.

    Returns
    -------
    None
    """
    words = [f"word{i}" for i in range(200)]
    long_text = " ".join(words)
    section = RawSection(title="Sec", level=1, text=long_text)
    chunks = chunk_section(section, max_tokens=50, overlap_tokens=10)
    if len(chunks) > 1:
        end_of_first = chunks[0].text.split()[-5:]
        start_of_second = chunks[1].text.split()[:20]
        overlap = set(end_of_first) & set(start_of_second)
        assert len(overlap) > 0


def test_chunk_section_sequence_indices_are_contiguous() -> None:
    """
    Verify chunk sequence indices are sequential starting from start_index.

    Returns
    -------
    None
    """
    long_text = " ".join(["word"] * 400)
    section = RawSection(title="Sec", level=1, text=long_text)
    chunks = chunk_section(section, max_tokens=80, overlap_tokens=10, start_index=5)
    indices = [c.sequence_index for c in chunks]
    assert indices == list(range(5, 5 + len(chunks)))


def test_chunk_document_returns_chunks_for_all_sections() -> None:
    """
    Verify document chunking traverses all sections in markdown document.

    Returns
    -------
    None
    """
    chunks = chunk_document(MARKDOWN_DOC, max_tokens=512, overlap_tokens=64)
    assert len(chunks) > 0
    full_text = " ".join(c.text for c in chunks)
    assert "Kant" in full_text
    assert "Hegel" in full_text


def test_chunk_document_sequence_indices_monotone() -> None:
    """
    Verify document chunk indices are monotonically increasing from 0.

    Returns
    -------
    None
    """
    chunks = chunk_document(MARKDOWN_DOC, max_tokens=100, overlap_tokens=10)
    indices = [c.sequence_index for c in chunks]
    assert indices == sorted(indices)
    assert indices == list(range(len(chunks)))


def test_chunk_section_uses_custom_token_counter() -> None:
    """
    Verify chunk_section honors custom token counter via dependency injection.

    Returns
    -------
    None
    """
    section = RawSection(
        title="Custom",
        level=1,
        text="Sentence one is here. Sentence two is here. Sentence three is here.",
    )
    # Custom counter: count words directly
    chunks = chunk_section(
        section,
        max_tokens=5,
        overlap_tokens=1,
        token_counter=lambda text: len(text.split()),
    )
    assert len(chunks) >= 2


def test_chunk_document_uses_custom_token_counter() -> None:
    """
    Verify chunk_document passes custom token counter to underlying sections.

    Returns
    -------
    None
    """
    chunks = chunk_document(
        MARKDOWN_DOC,
        max_tokens=20,
        overlap_tokens=5,
        token_counter=lambda text: len(text.split()),
    )
    assert len(chunks) > 1
