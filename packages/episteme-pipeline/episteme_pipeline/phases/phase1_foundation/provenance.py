"""
Deterministic ID generation and provenance helpers for Phase 1.

IDs are SHA-256 based so re-running the pipeline on the same input
produces the same IDs → MERGE writes to Neo4j are idempotent.

Identity rules
---------------------
``doc_id`` hashes the *canonical source path*, not the file stem. Hashing the
stem alone collapsed ``a/intro.md`` and ``b/intro.md`` into a single Document
node, silently interleaving two corpora.

``chunk_id`` deliberately keeps a fingerprint of the chunk text. Chunk identity
is content-addressed on purpose: the artifact fingerprint/reuse machinery, the
per-phase ``*_processed`` checkpoints and the embedding cache all key off the
chunk id, so an edited paragraph *must* produce a new id or the pipeline would
happily serve stale downstream results. The cost is that re-ingesting an edited
document leaves the previous chunk nodes behind; Phase 1 therefore prunes them
explicitly (see ``GraphWriter.prune_document_children``) instead of letting them
accumulate.

Provenance is split into two dictionaries because ``SET n += $props`` on every
run made the graph byte-unstable: ``ingested_at`` was rewritten on every node on
every run, so nothing was ever comparable across runs. ``base_provenance``
carries only values that are constant for a given source, and
``creation_provenance`` carries the first-seen timestamp, written through
``ON CREATE SET``. "Last seen" is a property of the run manifest, not of the
graph.
"""

import hashlib
from datetime import UTC, datetime
from pathlib import Path


def _sha(text: str, length: int = 12) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:length]


def canonical_source(source_path: Path) -> str:
    """Return the path spelling that document identity is derived from.

    Resolved to an absolute path first, so ``./data/x.md`` and
    ``/abs/data/x.md`` denote the same document, then made relative to the
    working directory when it lies underneath it, so identity survives moving
    the checkout to a different machine. Out-of-tree sources keep their
    absolute path.
    """
    resolved = Path(source_path).expanduser().resolve()
    try:
        return resolved.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return resolved.as_posix()


def doc_id(source_path: Path) -> str:
    # Hash the whole canonical path, not just the stem: two files named
    # ``intro.md`` in different directories are two documents (F-11).
    return f"doc_{_sha(canonical_source(source_path))}"


def chapter_id(d_id: str, title: str) -> str:
    return f"{d_id}_chap_{_sha(title)}"


def chunk_id(chap_id: str, sequence_index: int, text: str) -> str:
    # Include text fingerprint so a changed chunk gets a new ID. See the module
    # docstring: this is load-bearing for checkpointing and artifact reuse, and
    # the resulting stale nodes are pruned rather than tolerated.
    return f"{chap_id}_chunk_{sequence_index:04d}_{_sha(text[:200])}"


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


def base_provenance(source_path: Path) -> dict:
    """Provenance written on every upsert. Constant for a given source."""
    return {
        "source_path": canonical_source(source_path),
        "confidence": 1.0,
    }


def creation_provenance() -> dict:
    """Provenance written only when the node is first created (``ON CREATE SET``).

    Kept out of ``base_provenance`` so a re-run of an unchanged corpus does not
    rewrite every node's properties with a fresh timestamp (F-11).
    """
    return {"ingested_at": now_utc()}
