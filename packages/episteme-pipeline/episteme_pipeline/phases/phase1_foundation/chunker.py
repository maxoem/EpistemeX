"""
SemanticChunker module.

Splits Markdown text into chapters and chunks.
Chapter boundaries: level-1 and level-2 Markdown headers (# / ##).
Chunk boundaries: paragraph breaks (double newline), respecting max_tokens.
Overlap: last N tokens of the previous chunk are prepended to the next.

Token count is measured via tiktoken (cl100k_base) when available offline,
falling back to word count * 1.35 heuristic (empirically close to BPE counts
for dense philosophical prose in German/English).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

import nltk
import tiktoken

_HEADER_RE = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)

TokenCounter = Callable[[str], int]


@lru_cache(maxsize=1)
def _get_encoder() -> tiktoken.Encoding | None:
    """
    Retrieve tiktoken encoding once, caching failure to avoid network retries.

    Returns
    -------
    tiktoken.Encoding or None
        The cl100k_base encoding instance if available offline, otherwise None.
    """
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def _split_sentences(text: str) -> list[str]:
    """
    Split a paragraph into sentences using NLTK with regex fallback.

    Parameters
    ----------
    text : str
        The input paragraph text.

    Returns
    -------
    list of str
        Extracted sentence strings.
    """
    try:
        return nltk.sent_tokenize(text)
    except Exception:
        return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _count_tokens(text: str) -> int:
    """
    Count tokens accurately using cl100k_base with word-count fallback.

    Parameters
    ----------
    text : str
        Input string to measure.

    Returns
    -------
    int
        Estimated or exact token count.
    """
    enc = _get_encoder()
    if enc is not None:
        try:
            return len(enc.encode(text, disallowed_special=()))
        except Exception:
            pass
    return max(1, int(len(text.split()) * 1.35))


@dataclass
class RawSection:
    """
    A parsed document section delimited by Markdown headings.

    Attributes
    ----------
    title : str
        Header text of the section.
    text : str
        Body text of the section.
    level : int
        Header depth level (1 for #, 2 for ##).
    """

    title: str
    text: str
    level: int


@dataclass
class RawChunk:
    """
    A chunk extracted from a document section.

    Attributes
    ----------
    chapter_title : str
        Title of the parent section.
    text : str
        Text content of the chunk.
    sequence_index : int
        Zero-based monotonic sequence index within the document.
    """

    chapter_title: str
    text: str
    sequence_index: int


def parse_sections(markdown: str) -> list[RawSection]:
    """
    Split Markdown into sections at # and ## header boundaries.

    Content before the first header is assigned to an implicit "Preamble" section.

    Parameters
    ----------
    markdown : str
        Raw Markdown document string.

    Returns
    -------
    list of RawSection
        Parsed sections containing title, level, and text content.
    """
    sections: list[RawSection] = []
    last_end = 0
    last_title = "Preamble"
    last_level = 1

    for match in _HEADER_RE.finditer(markdown):
        content = markdown[last_end : match.start()].strip()
        if content:
            sections.append(RawSection(title=last_title, text=content, level=last_level))
        last_title = match.group(2).strip()
        last_level = len(match.group(1))
        last_end = match.end()

    tail = markdown[last_end:].strip()
    if tail:
        sections.append(RawSection(title=last_title, text=tail, level=last_level))

    return [s for s in sections if s.text]


def chunk_section(
    section: RawSection,
    max_tokens: int,
    overlap_tokens: int,
    start_index: int = 0,
    token_counter: TokenCounter = _count_tokens,
) -> list[RawChunk]:
    """
    Split a single section into chunks respecting max_tokens and overlap.

    Parameters
    ----------
    section : RawSection
        The section to split into chunks.
    max_tokens : int
        Maximum number of tokens allowed per chunk.
    overlap_tokens : int
        Target number of tokens to overlap between adjacent chunks.
    start_index : int, optional
        Starting chunk sequence index, by default 0.
    token_counter : TokenCounter, optional
        Callable computing token counts for text fragments, by default _count_tokens.

    Returns
    -------
    list of RawChunk
        Extracted sequential raw chunks.
    """
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", section.text) if p.strip()]

    # Flatten into a list of units (sentences) to guarantee we never exceed max_tokens
    units: list[str] = []
    for para in paragraphs:
        if token_counter(para) > max_tokens:
            units.extend(_split_sentences(para))
        else:
            units.append(para)

    chunks: list[RawChunk] = []
    current_units: list[str] = []
    current_tokens = 0
    seq = start_index

    for unit in units:
        unit_tokens = token_counter(unit)

        # If a single sentence is magically larger than max_tokens, we add it and move on
        if current_tokens + unit_tokens > max_tokens and current_units:
            chunks.append(
                RawChunk(
                    chapter_title=section.title,
                    text="\n\n".join(current_units),
                    sequence_index=seq,
                )
            )
            seq += 1

            # Build overlap from tail of current_units
            overlap_units: list[str] = []
            overlap_count = 0
            for u in reversed(current_units):
                ut = token_counter(u)
                if overlap_count + ut > overlap_tokens:
                    break
                overlap_units.insert(0, u)
                overlap_count += ut

            current_units = overlap_units
            current_tokens = overlap_count

        current_units.append(unit)
        current_tokens += unit_tokens

    if current_units:
        chunks.append(
            RawChunk(
                chapter_title=section.title,
                text="\n\n".join(current_units),
                sequence_index=seq,
            )
        )

    return chunks


def chunk_document(
    markdown: str,
    max_tokens: int = 1024,
    overlap_tokens: int = 128,
    token_counter: TokenCounter = _count_tokens,
) -> list[RawChunk]:
    """
    Split Markdown text into sections and chunks.

    Parameters
    ----------
    markdown : str
        Full Markdown document text.
    max_tokens : int, optional
        Maximum number of tokens per chunk, by default 1024.
    overlap_tokens : int, optional
        Overlap size in tokens between chunks, by default 128.
    token_counter : TokenCounter, optional
        Callable computing token counts, by default _count_tokens.

    Returns
    -------
    list of RawChunk
        List of sequential raw chunks across all parsed sections.
    """
    sections = parse_sections(markdown)
    all_chunks: list[RawChunk] = []
    for section in sections:
        section_chunks = chunk_section(
            section,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            start_index=len(all_chunks),
            token_counter=token_counter,
        )
        all_chunks.extend(section_chunks)
    return all_chunks
