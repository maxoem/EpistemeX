"""
Modular component for Topological Injection of textual envelopes.
Implements the O(1) span extraction and symmetrical truncation safeguard.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol

from episteme_pipeline.events.context import get_event_emitter
from episteme_pipeline.events.models import (
    EnvelopeInjectionAttempted,
    EnvelopeInjectionFailed,
)

logger = logging.getLogger(__name__)

class MentionContextInjector(Protocol):
    def inject(
        self,
        chunk_text: str,
        mention_name: str,
        mention_quote: str = "",
        chunk_id: str = "",
        max_chars: int = 512,
        **kwargs: Any,
    ) -> str | None:
        """
        Find the exact quote, symmetrically truncate, and inject [ENT] / [\\ENT] markers.
        Emits events on success/failure.
        """
        ...


class DefaultMentionContextInjector(MentionContextInjector):
    def inject(
        self,
        chunk_text: str,
        mention_name: str,
        mention_quote: str = "",
        chunk_id: str = "",
        max_chars: int = 512,
        **kwargs: Any,
    ) -> str | None:
        """
        Locates the mention quote or name in `chunk_text`. If found, extracts a symmetrically
        truncated window centered around the mention and injects topological markers.
        Falls back to normalized matching and mention_name if exact quote match fails.
        Emits events on attempt and failure.
        """
        if "max_length" in kwargs:
            max_chars = kwargs["max_length"]

        emitter = get_event_emitter()
        emitter.emit(EnvelopeInjectionAttempted(mention_name=mention_name, chunk_id=chunk_id))

        search_str = mention_quote or mention_name
        start_idx = chunk_text.find(search_str) if search_str else -1

        # Fallback B: Normalized Match with regex
        if start_idx == -1 and search_str:
            pattern = re.escape(search_str)
            pattern = re.sub(r'\\?["„“”«»]', r'["„“”«»]', pattern)
            pattern = re.sub(r'\\?[-–—]', r'[-–—]', pattern)
            pattern = re.sub(r'\\\s+', r'\\s+', pattern)
            pattern = re.sub(r'\\?\.\.\.|\\?…', r'(?:\\.\\.\\.|…)', pattern)
            match = re.search(pattern, chunk_text)
            if match:
                start_idx = match.start()
                search_str = match.group(0)

        # Fallback D: Mention Name Match
        if start_idx == -1 and mention_name and search_str != mention_name:
            search_str = mention_name
            start_idx = chunk_text.find(search_str)
            if start_idx == -1:
                pattern = re.escape(search_str)
                pattern = re.sub(r'\\?["„“”«»]', r'["„“”«»]', pattern)
                pattern = re.sub(r'\\?[-–—]', r'[-–—]', pattern)
                pattern = re.sub(r'\\\s+', r'\\s+', pattern)
                pattern = re.sub(r'\\?\.\.\.|\\?…', r'(?:\\.\\.\\.|…)', pattern)
                match = re.search(pattern, chunk_text)
                if match:
                    start_idx = match.start()
                    search_str = match.group(0)

        if start_idx == -1:
            logger.debug(
                f"Envelope injection failed for {mention_name} "
                f"(quote: {mention_quote[:30] if mention_quote else ''}...) in chunk {chunk_id}"
            )
            emitter.emit(EnvelopeInjectionFailed(
                mention_name=mention_name,
                mention_quote=mention_quote or "",
                chunk_id=chunk_id,
                reason="Quote and name both failed to match chunk text."
            ))
            return None

        end_idx = start_idx + len(search_str)

        # Symmetrical Truncation (Technical Safeguard)
        center = start_idx + len(search_str) // 2
        half_window = max_chars // 2

        window_start = max(0, center - half_window)
        window_end = min(len(chunk_text), center + half_window)

        # Adjust entity bounds relative to the new truncated window
        rel_start = max(0, start_idx - window_start)
        rel_end = min(window_end - window_start, end_idx - window_start)

        window_text = chunk_text[window_start:window_end]

        # Inject markers (Keeping markers as plain text, per L06 Option A recommendations)
        injected = (
            window_text[:rel_start]
            + "[ENT] "
            + window_text[rel_start:rel_end]
            + " [\\ENT]"
            + window_text[rel_end:]
        )
        return injected
