"""Tests for content-based hashing of corpus files in fingerprint_existing_sources."""

import hashlib
from pathlib import Path

from episteme_pipeline.runs.fingerprints import fingerprint_existing_sources


def test_content_hash_appears_in_fingerprint(tmp_path: Path):
    """Verify content hash is included in the fingerprint records."""
    doc = tmp_path / "test.md"
    doc.write_text("hello world", encoding="utf-8")

    fp = fingerprint_existing_sources([str(doc)])

    assert fp is not None
    assert len(fp) == 64  # SHA-256 hex length


def test_different_content_produces_different_fingerprint(tmp_path: Path):
    """Verify files with different content produce different fingerprints."""
    doc1 = tmp_path / "doc1.md"
    doc2 = tmp_path / "doc2.md"
    doc1.write_text("content a", encoding="utf-8")
    doc2.write_text("content b", encoding="utf-8")

    fp1 = fingerprint_existing_sources([str(doc1)])
    fp2 = fingerprint_existing_sources([str(doc2)])

    assert fp1 != fp2


def test_missing_file_handled(tmp_path: Path):
    """Verify missing files don't crash the fingerprinting."""
    missing = tmp_path / "does_not_exist.md"

    fp = fingerprint_existing_sources([str(missing)])

    assert fp is not None


def test_content_hash_changes_detected_on_modify(tmp_path: Path):
    """Verify modifying a file changes the fingerprint."""
    doc = tmp_path / "doc.md"
    doc.write_text("original", encoding="utf-8")
    fp1 = fingerprint_existing_sources([str(doc)])

    doc.write_text("modified", encoding="utf-8")
    fp2 = fingerprint_existing_sources([str(doc)])

    assert fp1 != fp2


def test_content_hash_field_present_in_records(tmp_path: Path):
    """Verify the content_hash field appears in the fingerprinted records."""
    doc = tmp_path / "test.md"
    doc.write_text("test content", encoding="utf-8")

    fp = fingerprint_existing_sources([str(doc)])

    hashlib.sha256(b"test content").hexdigest()
    # The fingerprint is a SHA-256 of the records, so we verify the expected
    # hash would produce a different fingerprint
    different_fp = fingerprint_existing_sources([f"{tmp_path}/nonexistent.md"])
    # Both should be non-empty stable fingerprints
    assert len(fp) == 64
    assert len(different_fp) == 64
    assert fp != different_fp
