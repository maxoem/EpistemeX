"""Tests for provenance ID generation (pure hash functions)."""

from pathlib import Path

from episteme_pipeline.phases.phase1_foundation.provenance import (
    chapter_id,
    chunk_id,
    doc_id,
)


def test_doc_id_is_deterministic():
    path = Path("/some/path/my_document.tex")
    assert doc_id(path) == doc_id(path)


def test_doc_id_differs_for_different_stems():
    assert doc_id(Path("a.tex")) != doc_id(Path("b.tex"))


def test_doc_id_has_prefix():
    result = doc_id(Path("kant_critique.tex"))
    assert result.startswith("doc_")


def test_chapter_id_is_deterministic():
    d_id = "doc_abc123"
    assert chapter_id(d_id, "Introduction") == chapter_id(d_id, "Introduction")


def test_chapter_id_differs_for_different_titles():
    d_id = "doc_abc123"
    assert chapter_id(d_id, "Introduction") != chapter_id(d_id, "Conclusion")


def test_chapter_id_differs_for_different_docs():
    assert chapter_id("doc_a", "Intro") != chapter_id("doc_b", "Intro")


def test_chunk_id_is_deterministic():
    chap_id = "doc_abc_chap_xyz"
    assert chunk_id(chap_id, 0, "text") == chunk_id(chap_id, 0, "text")


def test_chunk_id_differs_for_different_sequence_indices():
    chap_id = "doc_abc_chap_xyz"
    assert chunk_id(chap_id, 0, "same text") != chunk_id(chap_id, 1, "same text")


def test_chunk_id_differs_for_different_texts():
    chap_id = "doc_abc_chap_xyz"
    assert chunk_id(chap_id, 0, "text A") != chunk_id(chap_id, 0, "text B")


def test_all_ids_are_strings():
    p = Path("file.tex")
    d = doc_id(p)
    c = chapter_id(d, "Chapter 1")
    ch = chunk_id(c, 0, "some text")
    assert isinstance(d, str)
    assert isinstance(c, str)
    assert isinstance(ch, str)
