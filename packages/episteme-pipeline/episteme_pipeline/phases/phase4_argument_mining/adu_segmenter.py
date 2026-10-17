"""
LLMADUSegmenter — default ADUSegmenter implementation.

Uses LlamaIndex astructured_predict to identify Argumentative Discourse Units
and wrap them in <ACn>...</ACn> markup tags. On parsing failure the segmenter
returns (chunk_text, []) — no ADUs found — and logs a warning.
The chunk is still marked as processed to avoid infinite retry of non-argumentative
chunks (e.g. bibliography sections, tables of contents).
"""

from __future__ import annotations

import logging

from typing import Any

from episteme_pipeline.llm import ensure_structured_llm
from episteme_pipeline.phases.phase4_argument_mining.models import ADUSegmentationOutput
from episteme_pipeline.prompts.models import StructuredPromptBundle
from episteme_pipeline.protocols.argument_mining import ADUSegmenter

logger = logging.getLogger(__name__)


class LLMADUSegmenter(ADUSegmenter):
    """Default ADUSegmenter using structured LLM prediction.

    Parameters
    ----------
    llm : Any
        Underlying LLM facade or client.
    prompt_template : str | None, optional
        Raw prompt template string, by default None.
    prompts : StructuredPromptBundle | str | None, optional
        Structured prompt bundle or template string, by default None.
    """

    def __init__(
        self,
        llm: Any,
        prompt_template: str | None = None,
        prompts: StructuredPromptBundle | str | None = None,
    ) -> None:
        self.llm = ensure_structured_llm(llm)
        self.prompts: StructuredPromptBundle | str = prompts or prompt_template or ""
        self.prompt_template: str = (
            self.prompts
            if isinstance(self.prompts, str)
            else self.prompts.direct_template
        )

    async def segment(
        self,
        chunk_id: str,
        chunk_text: str,
    ) -> tuple[str, list[str]]:
        """Segment input text into Argumentative Discourse Units (ADUs).

        Parameters
        ----------
        chunk_id : str
            Identifier of the source chunk.
        chunk_text : str
            Raw text of the chunk.

        Returns
        -------
        tuple of (str, list of str)
            Tuple of tagged chunk text and extracted ADU IDs.
        """
        raw: ADUSegmentationOutput = await self.llm.predict_structured(
            ADUSegmentationOutput,
            self.prompts,
            chunk_text=chunk_text,
        )

        if not raw.adu_ids:
            logger.debug("No ADUs found in chunk %s", chunk_id)
            return chunk_text, []

        return raw.tagged_text, raw.adu_ids

    def fingerprint(self) -> dict[str, Any]:
        """Return deterministic ADU segmenter configuration.

        Returns
        -------
        dict of str to Any
            Dictionary containing class identifier, prompt template, and LLM fingerprint.
        """
        from typing import Any

        from episteme_pipeline.protocols.fingerprint import Fingerprintable
        from episteme_pipeline.runs.fingerprints import fingerprint_method

        return {
            "class": self.__class__.__name__,
            "prompt_template": self.prompt_template,
            "llm": (
                self.llm.fingerprint()
                if isinstance(self.llm, Fingerprintable)
                else fingerprint_method(self.llm)
            ),
        }

