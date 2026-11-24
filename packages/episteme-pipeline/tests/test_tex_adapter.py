"""Tests for the TeX source adapter."""

from __future__ import annotations

from pathlib import Path

from episteme_pipeline.phases.phase1_foundation.adapters.tex_adapter import TexAdapter


def test_tex_adapter_runs_pandoc_from_source_directory(
    monkeypatch, tmp_path: Path
) -> None:
    """Pandoc should be executed in the TeX file directory so includes resolve."""
    source_dir = tmp_path / "tex"
    source_dir.mkdir()
    source_path = source_dir / "main.tex"
    source_path.write_text("\\include{chapter.tex}\n", encoding="utf-8")
    bib_path = tmp_path / "refs.bib"
    bib_path.write_text("", encoding="utf-8")

    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs

        class Result:
            stdout = "# Title\n\nBody"

        return Result()

    monkeypatch.setattr(
        "episteme_pipeline.phases.phase1_foundation.adapters.tex_adapter.subprocess.run",
        fake_run,
    )

    output = TexAdapter().convert(source_path, bib_paths=[bib_path])

    assert output == "# Title\n\nBody"
    assert recorded["cmd"] == [
        "pandoc",
        "main.tex",
        "--to",
        "markdown",
        "--wrap=none",
        "--strip-comments",
        "--bibliography",
        str(bib_path.resolve()),
    ]
    assert recorded["kwargs"] == {
        "cwd": source_dir.resolve(),
        "capture_output": True,
        "text": True,
        "check": True,
        "timeout": 120,
    }


def test_tex_adapter_autodiscovers_bib_from_tex_command(
    monkeypatch, tmp_path: Path
) -> None:
    source_dir = tmp_path / "tex"
    source_dir.mkdir()
    source_path = source_dir / "paper.tex"
    source_path.write_text("\\bibliography{literature}\n", encoding="utf-8")
    bib_path = source_dir / "literature.bib"
    bib_path.write_text("@article{key, title={T}}", encoding="utf-8")

    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        recorded["cmd"] = cmd

        class Result:
            stdout = "# Paper"

        return Result()

    monkeypatch.setattr(
        "episteme_pipeline.phases.phase1_foundation.adapters.tex_adapter.subprocess.run",
        fake_run,
    )

    output = TexAdapter().convert(source_path)
    assert output == "# Paper"
    assert "--bibliography" in recorded["cmd"]
    assert str(bib_path.resolve()) in recorded["cmd"]


def test_tex_adapter_autodiscovers_bib_from_directory(
    monkeypatch, tmp_path: Path
) -> None:
    source_dir = tmp_path / "tex"
    source_dir.mkdir()
    source_path = source_dir / "paper.tex"
    source_path.write_text("\\section{Intro}\n", encoding="utf-8")
    bib_path = source_dir / "auto.bib"
    bib_path.write_text("@article{key, title={T}}", encoding="utf-8")

    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        recorded["cmd"] = cmd

        class Result:
            stdout = "# Paper"

        return Result()

    monkeypatch.setattr(
        "episteme_pipeline.phases.phase1_foundation.adapters.tex_adapter.subprocess.run",
        fake_run,
    )

    output = TexAdapter().convert(source_path)
    assert output == "# Paper"
    assert "--bibliography" in recorded["cmd"]
    assert str(bib_path.resolve()) in recorded["cmd"]
