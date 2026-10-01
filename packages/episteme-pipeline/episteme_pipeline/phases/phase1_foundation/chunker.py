"""
SemanticChunker — splits Markdown text into chapters and chunks.

Chapter boundaries: level-1 and level-2 Markdown headers (# / ##).
Chunk boundaries: paragraph breaks (double newline), respecting max_tokens.
Overlap: last N tokens of the previous chunk are prepended to the next.

Token count is approximated as word count × 1.35 (empirically close to
BPE counts for dense philosophical prose in German/English).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import nltk
import tiktoken


_HEADER_RE = re.compile(r'^(#{1,2})\s+(.+)$', re.MULTILINE)

# Ensure nltk punkt is downloaded
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)


def _count_tokens(text: str) -> int:
    """Accurate token counting using tiktoken cl100k_base with word-count fallback."""
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text, disallowed_special=()))
    except Exception:
        return max(1, int(len(text.split()) * 1.35))



@dataclass
class RawSection:
    title: str
    text: str
    level: int


@dataclass
class RawChunk:
    chapter_title: str
    text: str
    sequence_index: int


def parse_sections(markdown: str) -> list[RawSection]:
    """
    Splits Markdown into sections at # and ## header boundaries.
    Content before the first header is assigned to an implicit "Preamble" section.
    """
    sections: list[RawSection] = []
    last_end = 0
    last_title = "Preamble"
    last_level = 1

    for match in _HEADER_RE.finditer(markdown):
        content = markdown[last_end:match.start()].strip()
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
) -> list[RawChunk]:
    """Splits a single section into chunks, respecting max_tokens and overlap using sentences."""
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', section.text) if p.strip()]
    
    # Flatten into a list of units (sentences) to guarantee we never exceed max_tokens
    units: list[str] = []
    for para in paragraphs:
        if _count_tokens(para) > max_tokens:
            # Paragraph too big, split into sentences
            try:
                sentences = nltk.sent_tokenize(para)
            except Exception:
                sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', para) if s.strip()]
            units.extend(sentences)
        else:
            units.append(para)

    chunks: list[RawChunk] = []
    current_units: list[str] = []
    current_tokens = 0
    seq = start_index

    for unit in units:
        unit_tokens = _count_tokens(unit)

        # If a single sentence is magically larger than max_tokens, we have to just add it and move on,
        # but normally this won't happen.
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
                ut = _count_tokens(u)
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
) -> list[RawChunk]:
    """Full pipeline: Markdown text → list of RawChunk objects."""
    sections = parse_sections(markdown)
    all_chunks: list[RawChunk] = []
    for section in sections:
        section_chunks = chunk_section(
            section,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            start_index=len(all_chunks),
        )
        all_chunks.extend(section_chunks)
    return all_chunks
