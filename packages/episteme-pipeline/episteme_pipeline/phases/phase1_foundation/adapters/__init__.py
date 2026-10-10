from pathlib import Path

from episteme_pipeline.phases.phase1_foundation.adapters.markdown_adapter import (
    MarkdownAdapter,
    PlainTextAdapter,
)
from episteme_pipeline.phases.phase1_foundation.adapters.tex_adapter import TexAdapter
from episteme_pipeline.protocols.data_source import DataSourceAdapter

DEFAULT_ADAPTERS: list[DataSourceAdapter] = [
    TexAdapter(),
    MarkdownAdapter(),
    PlainTextAdapter(),
]


def find_adapter(
    path: Path,
    adapters: list[DataSourceAdapter] = DEFAULT_ADAPTERS,
) -> DataSourceAdapter:
    for adapter in adapters:
        if adapter.can_handle(path):
            return adapter
    raise ValueError(
        f"No adapter found for {path.suffix!r}. "
        f"Register a custom DataSourceAdapter in Phase1Runner(adapters=...)."
    )


__all__ = [
    "DEFAULT_ADAPTERS",
    "DataSourceAdapter",
    "MarkdownAdapter",
    "PlainTextAdapter",
    "TexAdapter",
    "find_adapter",
]
