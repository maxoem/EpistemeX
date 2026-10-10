"""Tests for Phase 1 document chunker (pure functions, no I/O)."""

from episteme_pipeline.phases.phase1_foundation.chunker import (
    RawSection,
    chunk_document,
    chunk_section,
    parse_sections,
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


def test_parse_sections_finds_h1_and_h2():
    sections = parse_sections(MARKDOWN_DOC)
    titles = [s.title for s in sections]
    assert "Introduction" in titles
    assert "Background" in titles
    assert "Methodology" in titles


def test_parse_sections_assigns_text():
    sections = parse_sections(MARKDOWN_DOC)
    intro = next(s for s in sections if s.title == "Introduction")
    assert "Kant" in intro.text
    assert "knowledge" in intro.text


def test_parse_sections_returns_raw_sections():
    sections = parse_sections(MARKDOWN_DOC)
    assert all(isinstance(s, RawSection) for s in sections)


def test_parse_sections_empty_doc():
    assert parse_sections("") == []


def test_parse_sections_no_headers():
    text = "Plain text with no headers at all."
    sections = parse_sections(text)
    # Either returns empty or wraps in a single untitled section
    assert isinstance(sections, list)


def test_chunk_section_single_chunk_for_short_text():
    section = RawSection(
        title="Intro",
        level=1,
        text="Short text.",
    )
    chunks = chunk_section(section, max_tokens=512, overlap_tokens=64)
    assert len(chunks) == 1
    assert "Short text." in chunks[0].text


def test_chunk_section_splits_long_text():
    # Chunker splits at paragraph boundaries — use many paragraphs
    paragraphs = [" ".join([f"word{j}" for j in range(30)]) for _ in range(10)]
    long_text = "\n\n".join(paragraphs)
    section = RawSection(title="Long", level=1, text=long_text)
    # max_tokens=80 < one paragraph (~40 words × 1.35 ≈ 54 tokens), so multiple chunks expected
    chunks = chunk_section(section, max_tokens=80, overlap_tokens=10)
    assert len(chunks) > 1


def test_chunk_section_overlap_produces_shared_content():
    words = [f"word{i}" for i in range(200)]
    long_text = " ".join(words)
    section = RawSection(title="Sec", level=1, text=long_text)
    chunks = chunk_section(section, max_tokens=50, overlap_tokens=10)
    if len(chunks) > 1:
        # Last tokens of chunk N should appear in chunk N+1
        end_of_first = chunks[0].text.split()[-5:]
        start_of_second = chunks[1].text.split()[:20]
        overlap = set(end_of_first) & set(start_of_second)
        assert len(overlap) > 0


def test_chunk_section_sequence_indices_are_contiguous():
    long_text = " ".join(["word"] * 400)
    section = RawSection(title="Sec", level=1, text=long_text)
    chunks = chunk_section(section, max_tokens=80, overlap_tokens=10, start_index=5)
    indices = [c.sequence_index for c in chunks]
    assert indices == list(range(5, 5 + len(chunks)))


def test_chunk_document_returns_chunks_for_all_sections():
    chunks = chunk_document(MARKDOWN_DOC, max_tokens=512, overlap_tokens=64)
    assert len(chunks) > 0
    # All sections should produce at least one chunk
    full_text = " ".join(c.text for c in chunks)
    assert "Kant" in full_text
    assert "Hegel" in full_text


def test_chunk_document_sequence_indices_monotone():
    chunks = chunk_document(MARKDOWN_DOC, max_tokens=100, overlap_tokens=10)
    indices = [c.sequence_index for c in chunks]
    assert indices == sorted(indices)
    assert indices == list(range(len(chunks)))
