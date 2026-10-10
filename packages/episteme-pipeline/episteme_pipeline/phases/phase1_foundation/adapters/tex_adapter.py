"""
TexAdapter — converts LaTeX files to clean Markdown via Pandoc.

Pandoc is called as a subprocess. Requires Pandoc >= 3.x to be installed.
Bibliography files (.bib) are resolved and passed to Pandoc so that citation
keys in the text are expanded to author-year references, giving the LLM the
citation context it needs for extraction.

Pandoc flags used:
  --wrap=none          Disable line wrapping (preserve paragraph structure)
  --strip-comments     Remove LaTeX comments
  --bibliography=...   Inject bib file(s) for citation expansion
"""

import re
import subprocess
from pathlib import Path

from episteme_pipeline.protocols.data_source import DataSourceAdapter

_LATEX_ARTIFACT_RE = re.compile(
    r'\\(?:label|ref|eqref|vspace|hspace|noindent|newpage|clearpage|'
    r'centering|begin|end|includegraphics|caption|footnote)\{[^}]*\}',
    re.IGNORECASE,
)
_BLANK_LINES_RE = re.compile(r'\n{3,}')


_BIBLIOGRAPHY_RE = re.compile(
    r'\\(?:bibliography|addbibresource)\{([^}]+)\}',
    re.IGNORECASE,
)


class TexAdapter(DataSourceAdapter):
    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() == '.tex'

    def convert(self, path: Path, bib_paths: list[Path] | None = None) -> str:
        source_path = path.expanduser().resolve()
        cmd = [
            'pandoc',
            source_path.name,
            '--to', 'markdown',
            '--wrap=none',
            '--strip-comments',
        ]
        resolved_bibs = list(bib_paths) if bib_paths else self._discover_bib_paths(source_path)
        for bib in resolved_bibs:
            cmd.extend(['--bibliography', str(bib.expanduser().resolve())])

        try:
            result = subprocess.run(
                cmd,
                cwd=source_path.parent,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Pandoc failed on {path}: {e.stderr[:500]}"
            ) from e
        except FileNotFoundError:
            raise RuntimeError(
                "Pandoc not found. Install it: https://pandoc.org/installing.html"
            )

        return self._clean(result.stdout)

    def _clean(self, text: str) -> str:
        # Remove residual LaTeX artifacts Pandoc doesn't fully convert
        text = _LATEX_ARTIFACT_RE.sub('', text)
        # Collapse excess blank lines
        text = _BLANK_LINES_RE.sub('\n\n', text)
        return text.strip()

    def _discover_bib_paths(self, source_path: Path) -> list[Path]:
        """Auto-discover bibliography (.bib) files relative to the TeX source document.

        Checks TeX content for ``\\bibliography{...}`` or ``\\addbibresource{...}``
        declarations. If none are found or referenced files do not exist, falls back to
        finding any ``.bib`` files in the source directory.
        """
        discovered: list[Path] = []
        if source_path.exists():
            try:
                content = source_path.read_text(encoding="utf-8", errors="ignore")
                for match in _BIBLIOGRAPHY_RE.finditer(content):
                    raw_entry = match.group(1)
                    for item in raw_entry.split(","):
                        item = item.strip()
                        if not item:
                            continue
                        bib_file = item if item.lower().endswith(".bib") else f"{item}.bib"
                        candidate = (source_path.parent / bib_file).resolve()
                        if candidate.exists() and candidate not in discovered:
                            discovered.append(candidate)
            except Exception:
                pass

        if not discovered and source_path.parent.exists():
            for candidate in sorted(source_path.parent.glob("*.bib")):
                resolved = candidate.resolve()
                if resolved not in discovered:
                    discovered.append(resolved)

        return discovered

