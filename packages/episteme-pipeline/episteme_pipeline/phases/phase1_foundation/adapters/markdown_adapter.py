import re
from pathlib import Path

from episteme_pipeline.protocols.data_source import DataSourceAdapter

_BLANK_LINES_RE = re.compile(r'\n{3,}')
_HTML_COMMENT_RE = re.compile(r'<!--.*?-->', re.DOTALL)


class MarkdownAdapter(DataSourceAdapter):
    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in {'.md', '.markdown'}

    def convert(self, path: Path, bib_paths: list[Path] | None = None) -> str:
        text = path.read_text(encoding='utf-8')
        text = _HTML_COMMENT_RE.sub('', text)
        text = _BLANK_LINES_RE.sub('\n\n', text)
        return text.strip()


class PlainTextAdapter(DataSourceAdapter):
    """Wraps plain-text files as a single Markdown section."""

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in {'.txt', '.text', ''}

    def convert(self, path: Path, bib_paths: list[Path] | None = None) -> str:
        text = path.read_text(encoding='utf-8')
        text = _BLANK_LINES_RE.sub('\n\n', text)
        return text.strip()
