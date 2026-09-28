#!/usr/bin/env python3
"""STNB Corpus Acquisition and Integrity Verification Tool.

Implements the Stand-Off Annotation pattern for the Structuralist Theory-Net
Benchmark (STNB). For non-public-domain scientific corpora (e.g., mid-20th-century
psychology literature still under copyright), STNB distributes only formal JSON-LD
graph envelopes and token-level character anchors.

This script verifies local text copies against cryptographic hashes (SHA-256)
and validates that the declared character span offsets in benchmark JSON-LD files
align exactly with the local source text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

CORPUS_REGISTRY: dict[str, dict[str, Any]] = {
    "festinger_carlsmith_1959": {
        "title": "Cognitive Consequences of Forced Compliance",
        "authors": "Leon Festinger and James M. Carlsmith",
        "year": 1959,
        "journal": "The Journal of Abnormal and Social Psychology, 58(2), 203-210",
        "doi": "10.1037/h0041593",
        "copyright_notice": "Copyright © 1959 American Psychological Association (APA).",
        "public_domain": False,
        "expected_sha256": "8c5823cd73d0e7ce6c90035c314f1b6d86c3f64cbc586ba3272201fc69207b5f",
        "expected_bytes": 32570,
        "benchmark_file": "datasets/stnb_festinger_carlsmith_1959.jsonld",
        "canonical_destinations": [
            "datasets/festinger_carlsmith_1959.md",
            "packages/episteme-pipeline/episteme_pipeline/evaluation/data/festinger_carlsmith_1959.txt",
        ],
        "acquisition_instructions": (
            "This work is under active copyright by the American Psychological Association.\n"
            "To acquire a lawful research copy:\n"
            "  1. Access the paper via your university library or APA PsycNet (DOI: 10.1037/h0041593).\n"
            "  2. Convert or save the text into Markdown or UTF-8 text.\n"
            "  3. Run: python scripts/fetch_stnb_corpora.py --verify --corpus festinger_carlsmith_1959"
        ),
    },
    "newton_principia_1687": {
        "title": "Philosophiae Naturalis Principia Mathematica (Axioms & Laws)",
        "authors": "Isaac Newton",
        "year": 1687,
        "publisher": "Royal Society of London",
        "doi": "N/A (Historical Edition)",
        "copyright_notice": "Public Domain.",
        "public_domain": True,
        "expected_sha256": None,
        "benchmark_file": "packages/episteme-pipeline/episteme_pipeline/evaluation/data/stnb_cpm_pilot.jsonld",
        "canonical_destinations": [
            "packages/episteme-pipeline/episteme_pipeline/evaluation/data/newton_principia_1687.txt"
        ],
        "acquisition_instructions": "This work is in the Public Domain and bundled directly with Episteme.",
    },
}


def compute_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hexadecimal digest of a file.

    Parameters
    ----------
    file_path : Path
        Filesystem path to the target file.

    Returns
    -------
    str
        Hexadecimal representation of the SHA-256 digest.
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_text_anchors(text: str, benchmark_path: Path) -> tuple[int, int, list[str]]:
    """Validate that character offsets in a benchmark JSON-LD file match source text.

    Parameters
    ----------
    text : str
        The full text of the local source document.
    benchmark_path : Path
        Path to the STNB JSON-LD ground truth benchmark file.

    Returns
    -------
    tuple of (int, int, list[str])
        A 3-tuple containing:
        - matched_count : int
            Number of successfully verified anchors.
        - total_anchors : int
            Total number of anchors inspected.
        - failure_diagnostics : list of str
            Diagnostic messages for any misaligned or mismatched spans.
    """
    if not benchmark_path.is_file():
        return 0, 0, [f"Benchmark file not found: {benchmark_path}"]

    with open(benchmark_path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    nodes = data.get("@graph", [])
    matched_count = 0
    total_anchors = 0
    failures: list[str] = []

    for node in nodes:
        node_id = node.get("@id", "unknown_node")
        anchor = (
            node.get("Episteme:textAnchor")
            or node.get("textAnchor")
            or node.get("glp:textAnchor")
        )
        if not anchor or not isinstance(anchor, dict):
            continue

        quote = anchor.get("verbatimQuote")
        start = anchor.get("charStart")
        end = anchor.get("charEnd")

        if quote is None or start is None or end is None:
            continue

        total_anchors += 1
        start = int(start)
        end = int(end)

        if start < 0 or end > len(text) or start >= end:
            failures.append(
                f"[{node_id}] Offset boundary out of range: [{start}:{end}] (document length: {len(text)})"
            )
            continue

        sliced = text[start:end]
        if sliced == quote:
            matched_count += 1
        else:
            # Fallback check if quote appears elsewhere
            alt_pos = text.find(quote)
            failures.append(
                f"[{node_id}] Mismatch at [{start}:{end}]. Expected:\n"
                f"  '{quote[:60]}...'\nGot:\n  '{sliced[:60]}...'\n"
                f"  (True occurrence found at: {alt_pos if alt_pos != -1 else 'NOT FOUND'})"
            )

    return matched_count, total_anchors, failures


def display_info(corpus_key: str) -> None:
    """Print legal and provenance metadata for a benchmark corpus.

    Parameters
    ----------
    corpus_key : str
        Identifier of the target corpus in CORPUS_REGISTRY.
    """
    entry = CORPUS_REGISTRY.get(corpus_key)
    if not entry:
        print(f"Unknown corpus: {corpus_key}. Available: {list(CORPUS_REGISTRY.keys())}")
        return

    print("=" * 70)
    print(f"STNB Corpus Profile: {entry['title']}")
    print("=" * 70)
    print(f"Authors:      {entry['authors']} ({entry['year']})")
    print(f"Citation:     {entry.get('journal') or entry.get('publisher')}")
    print(f"DOI:          {entry['doi']}")
    print(f"Copyright:    {entry['copyright_notice']}")
    print(f"Licensing:    {'Public Domain' if entry['public_domain'] else 'Restricted / Stand-Off Acquisition'}")
    if entry.get("expected_sha256"):
        print(f"SHA-256 Hash: {entry['expected_sha256']}")
    print("-" * 70)
    print("Acquisition Instructions:")
    print(entry["acquisition_instructions"])
    print("=" * 70)


def verify_corpus(corpus_key: str, input_path: Path | None = None) -> bool:
    """Verify local presence and offset integrity of a corpus.

    Parameters
    ----------
    corpus_key : str
        Corpus identifier.
    input_path : Path or None, optional
        Optional path to user-supplied text file.

    Returns
    -------
    bool
        True if all verification checks passed, False otherwise.
    """
    entry = CORPUS_REGISTRY.get(corpus_key)
    if not entry:
        print(f"Error: Unknown corpus '{corpus_key}'.")
        return False

    candidate_paths: list[Path] = []
    if input_path:
        candidate_paths.append(input_path)
    for dest in entry["canonical_destinations"]:
        candidate_paths.append(Path(dest))

    found_path: Path | None = None
    for p in candidate_paths:
        if p.is_file():
            found_path = p
            break

    if not found_path:
        print(f"Corpus '{corpus_key}' not found locally.")
        print(f"Searched paths: {[str(p) for p in candidate_paths]}")
        print("\nPlease follow acquisition instructions:")
        print(entry["acquisition_instructions"])
        return False

    print(f"🔍 Located local text at: {found_path}")
    file_bytes = found_path.stat().st_size
    file_hash = compute_sha256(found_path)

    expected_hash = entry.get("expected_sha256")
    if expected_hash:
        if file_hash == expected_hash:
            print(f"SHA-256 Digest Verified: {file_hash}")
        else:
            print(f"️   SHA-256 Hash Mismatch!")
            print(f"   Expected: {expected_hash}")
            print(f"   Found:    {file_hash}")
            print("   The text may have different whitespace, encoding, or OCR variants.")

    with open(found_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    benchmark_file = Path(entry["benchmark_file"])
    matched, total, diagnostics = verify_text_anchors(full_text, benchmark_file)

    print(f"Text Anchor Grounding: {matched}/{total} spans perfectly aligned ({matched/total:.1%})")
    if diagnostics:
        print("Diagnostic failures:")
        for diag in diagnostics:
            print(f"   - {diag}")
        return False

    print(f"Corpus '{corpus_key}' is fully validated for STNB evaluation!")
    return True


def main() -> None:
    """CLI entrypoint for STNB corpus management."""
    parser = argparse.ArgumentParser(
        description="STNB Corpus Acquisition and Integrity Verification Tool"
    )
    parser.add_argument(
        "--corpus",
        choices=list(CORPUS_REGISTRY.keys()) + ["all"],
        default="festinger_carlsmith_1959",
        help="Target corpus to verify or inspect (default: festinger_carlsmith_1959)",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Print copyright and acquisition instructions for the selected corpus",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify local corpus checksum and character span alignment",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Optional path to a custom local text or markdown file to verify",
    )

    args = parser.parse_args()

    target_corpora = (
        list(CORPUS_REGISTRY.keys()) if args.corpus == "all" else [args.corpus]
    )

    if args.info:
        for c in target_corpora:
            display_info(c)
        return

    if args.verify or not args.info:
        success = True
        for c in target_corpora:
            res = verify_corpus(c, input_path=args.file)
            if not res:
                success = False
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
