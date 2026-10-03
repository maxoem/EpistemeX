r"""Format and validate LaTeX math environments in Markdown documentation.

This module provides verification and transformation utilities for LaTeX math
delimiters in Markdown files:
1. Transforms raw LaTeX bracket display math (`\[ ... \]`) to standard Markdown math
   delimiters before executing downstream normalization:
   - Replaces with inline math (`$ ... $`) inside Markdown tables.
   - Replaces with display math (`$$ ... $$`) outside tables.
2. Replaces display math (`$$ ... $$`) with inline math (`$ ... $`) inside Markdown tables,
   preventing broken table layout in Markdown parsers (MathJax / KaTeX / Python-Markdown).
3. Verifies and ensures that all display math (`$$ ... $$`) environments outside tables
   start at the beginning of a line with NO leading whitespace (column 0), preventing
   Markdown parsers from treating indented formulas as code blocks.

Docstrings adhere to the NumPy documentation standard.
"""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path
import re
from typing import NamedTuple


class MathIssue(NamedTuple):
    """Container describing a math environment formatting issue.

    Attributes
    ----------
    line_number : int
        1-based line number where the issue was detected.
    issue_type : str
        Type of issue ('table_display_math', 'math_not_at_line_start',
        'display_bracket_math', or 'table_bracket_math').
    content : str
        The raw line content containing the violation.
    description : str
        Human-readable explanation of the issue.
    """

    line_number: int
    issue_type: str
    content: str
    description: str


def is_table_row(line: str) -> bool:
    """Determine whether a line is a Markdown table row.

    Parameters
    ----------
    line : str
        Single line of markdown text.

    Returns
    -------
    bool
        True if the line represents a Markdown table row delimited by pipe characters.
    """
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def check_bracket_math(content: str) -> list[MathIssue]:
    r"""Check for LaTeX bracket math delimiters '\[' and '\]'.

    Parameters
    ----------
    content : str
        Full markdown document text.

    Returns
    -------
    list of MathIssue
        List of identified issues where '\[' or '\]' are used.
    """
    issues: list[MathIssue] = []
    lines = content.splitlines()
    in_code_fence = False

    for idx, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue

        has_open = bool(re.search(r"(?<!\\)\\\[", line))
        has_close = bool(re.search(r"(?<!\\)\\\]", line))
        if has_open or has_close:
            if is_table_row(line):
                desc = (
                    r"LaTeX bracket math delimiter '\[ ... \]' used inside Markdown table row; "
                    "should be inline '$ ... $'"
                )
                issue_type = "table_bracket_math"
            else:
                desc = (
                    r"LaTeX bracket math delimiter '\[ ... \]' used; "
                    "should be display math '$$ ... $$'"
                )
                issue_type = "display_bracket_math"

            issues.append(
                MathIssue(
                    line_number=idx,
                    issue_type=issue_type,
                    content=line,
                    description=desc,
                )
            )

    return issues


def replace_bracket_math(content: str) -> tuple[str, int]:
    r"""Replace LaTeX bracket math delimiters '\[' and '\]' with '$$' or '$'.

    Inside Markdown tables, delimiters are transformed to inline math ('$').
    Outside tables, delimiters are transformed to display math ('$$').

    Parameters
    ----------
    content : str
        Full markdown document text.

    Returns
    -------
    tuple of (str, int)
        The transformed document text and the count of modified lines.
    """
    lines = content.splitlines()
    new_lines: list[str] = []
    in_code_fence = False
    replaced_lines = 0

    for line in lines:
        if line.strip().startswith("```"):
            in_code_fence = not in_code_fence
            new_lines.append(line)
            continue
        if in_code_fence:
            new_lines.append(line)
            continue

        has_open = bool(re.search(r"(?<!\\)\\\[", line))
        has_close = bool(re.search(r"(?<!\\)\\\]", line))

        if not (has_open or has_close):
            new_lines.append(line)
            continue

        if is_table_row(line):
            fixed_line = re.sub(r"(?<!\\)\\\[", "$", line)
            fixed_line = re.sub(r"(?<!\\)\\\]", "$", fixed_line)
        else:
            fixed_line = re.sub(r"(?<!\\)\\\[", "$$", line)
            fixed_line = re.sub(r"(?<!\\)\\\]", "$$", fixed_line)

        new_lines.append(fixed_line)
        replaced_lines += 1

    result = "\n".join(new_lines)
    if content.endswith("\n"):
        result += "\n"
    return result, replaced_lines


def check_math_in_tables(content: str) -> list[MathIssue]:
    """Check whether '$$ ... $$' display math is used within Markdown tables.

    Parameters
    ----------
    content : str
        Full markdown document text.

    Returns
    -------
    list of MathIssue
        List of identified issues where '$$' is used in table rows.
    """
    issues: list[MathIssue] = []
    in_code_fence = False

    for idx, line in enumerate(content.splitlines(), start=1):
        if line.strip().startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue

        if is_table_row(line) and re.search(r"(?<!\\)(?<!\$)\$\$(?!\$)", line):
            issues.append(
                MathIssue(
                    line_number=idx,
                    issue_type="table_display_math",
                    content=line,
                    description="Display math '$$ ... $$' used inside Markdown table row; should be inline '$ ... $'",
                )
            )

    return issues


def replace_table_math(content: str) -> tuple[str, int]:
    """Replace '$$' with '$' inside Markdown table rows.

    Parameters
    ----------
    content : str
        Full markdown document text.

    Returns
    -------
    tuple of (str, int)
        The transformed document text and the count of table rows modified.
    """
    lines = content.splitlines()
    new_lines: list[str] = []
    in_code_fence = False
    replaced_rows = 0

    for line in lines:
        if line.strip().startswith("```"):
            in_code_fence = not in_code_fence
            new_lines.append(line)
            continue
        if in_code_fence:
            new_lines.append(line)
            continue

        if is_table_row(line):
            if re.search(r"(?<!\\)(?<!\$)\$\$(?!\$)", line):
                fixed_line = re.sub(r"(?<!\\)(?<!\$)\$\$(?!\$)", "$", line)
                new_lines.append(fixed_line)
                replaced_rows += 1
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    result = "\n".join(new_lines)
    if content.endswith("\n"):
        result += "\n"
    return result, replaced_rows


def check_display_math_line_start(content: str) -> list[MathIssue]:
    """Verify if all '$$...$$' environments outside tables begin at column 0 without whitespace.

    The opening '$$' must be at the very beginning of the line (column 0, or preceded only
    by blockquote markers such as '> '). Any leading indentation (e.g. 2 or 4 spaces)
    triggers code-block interpretation in Markdown parsers and is flagged as an issue.

    Parameters
    ----------
    content : str
        Full markdown document text.

    Returns
    -------
    list of MathIssue
        List of identified issues where '$$' has non-permitted whitespace or preceding text.
    """
    issues: list[MathIssue] = []
    lines = content.splitlines()
    in_code_fence = False
    in_math_block = False

    for idx, line in enumerate(lines, start=1):
        if line.strip().startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence or is_table_row(line):
            continue

        matches = list(re.finditer(r"(?<!\\)(?<!\$)\$\$(?!\$)", line))
        if not matches:
            continue

        bq_match = re.match(r"^(\s*(?:>\s*)*)", line)
        bq_prefix = bq_match.group(1).lstrip() if bq_match and ">" in bq_match.group(1) else ""

        if in_math_block:
            in_math_block = False
            m_close = matches[0]
            prefix = line[:m_close.start()]
            clean_prefix = re.sub(r"^(\s*(?:>\s*)*)", "", prefix)
            trailing = line[m_close.end():]

            if clean_prefix == "" and (prefix != bq_prefix or trailing.strip()):
                desc = (
                    f"Display math closing '$$' has non-permitted leading whitespace ({len(prefix)} spaces); "
                    "must start at the beginning of the line with no whitespaces"
                    if prefix != bq_prefix
                    else "Display math closing '$$' has trailing text on the same line; should be placed on its own line"
                )
                issues.append(
                    MathIssue(
                        line_number=idx,
                        issue_type="math_not_at_line_start",
                        content=line,
                        description=desc,
                    )
                )

            if len(matches) % 2 == 0:
                in_math_block = True
        else:
            m0 = matches[0]
            prefix = line[:m0.start()]
            clean_prefix = re.sub(r"^(\s*(?:>\s*)*)", "", prefix)

            if clean_prefix != "":
                issues.append(
                    MathIssue(
                        line_number=idx,
                        issue_type="math_not_at_line_start",
                        content=line,
                        description=(
                            f"Display math opening '$$' preceded by text '{clean_prefix.strip()}'; "
                            "must be placed at the beginning of a new line with no whitespaces"
                        ),
                    )
                )
            elif prefix != bq_prefix:
                issues.append(
                    MathIssue(
                        line_number=idx,
                        issue_type="math_not_at_line_start",
                        content=line,
                        description=(
                            f"Display math opening '$$' has non-permitted leading whitespace ({len(prefix)} spaces); "
                            "must start at the beginning of the line with no whitespaces"
                        ),
                    )
                )

            if len(matches) % 2 == 1:
                in_math_block = True

    return issues


def fix_display_math_line_start(
    content: str, collapse_single_line: bool = False
) -> tuple[str, int]:
    """Place display math '$$' environments at the beginning of a line with zero leading whitespace.

    Parameters
    ----------
    content : str
        Full markdown document text.
    collapse_single_line : bool, default=False
        If True, collapses multiline blocks containing a single equation line into '$$ formula $$'.

    Returns
    -------
    tuple of (str, int)
        The transformed document text and the count of adjusted math lines.
    """
    lines = content.splitlines()
    new_lines: list[str] = []
    in_code_fence = False
    in_math_block = False
    fixed_count = 0

    for line in lines:
        if line.strip().startswith("```"):
            in_code_fence = not in_code_fence
            new_lines.append(line)
            continue
        if in_code_fence or is_table_row(line):
            new_lines.append(line)
            continue

        matches = list(re.finditer(r"(?<!\\)(?<!\$)\$\$(?!\$)", line))
        if not matches:
            new_lines.append(line)
            continue

        bq_match = re.match(r"^(\s*(?:>\s*)*)", line)
        bq_prefix = bq_match.group(1).lstrip() if bq_match and ">" in bq_match.group(1) else ""

        if in_math_block:
            in_math_block = False
            m_close = matches[0]
            prefix = line[:m_close.start()]
            clean_prefix = re.sub(r"^(\s*(?:>\s*)*)", "", prefix)
            trailing = line[m_close.end():]

            if clean_prefix == "" and (prefix != bq_prefix or trailing.strip()):
                fixed_count += 1
                new_lines.append(f"{bq_prefix}$$")
                if trailing.strip():
                    new_lines.append(f"{bq_prefix}{trailing.lstrip()}")
            elif trailing.strip():
                fixed_count += 1
                new_lines.append(line[:m_close.end()])
                new_lines.append(f"{bq_prefix}{trailing.lstrip()}")
            else:
                new_lines.append(line)

            if len(matches) % 2 == 0:
                in_math_block = True
        else:
            m0 = matches[0]
            prefix = line[:m0.start()]
            clean_prefix = re.sub(r"^(\s*(?:>\s*)*)", "", prefix)

            if clean_prefix == "" and prefix == bq_prefix:
                # Opening $$ is already at start of line with NO leading whitespace
                if len(matches) % 2 == 1:
                    in_math_block = True
                new_lines.append(line)
            elif clean_prefix == "" and prefix != bq_prefix:
                # Opening $$ has leading whitespace (e.g. "   $$")
                fixed_count += 1
                new_line = f"{bq_prefix}{line.lstrip()}"
                if len(matches) % 2 == 1:
                    in_math_block = True
                new_lines.append(new_line)
            else:
                # Opening $$ preceded by text (e.g. "cluster $l \in L$: $$")
                fixed_count += 1
                before = prefix.rstrip()
                new_lines.append(before)

                rest = line[m0.start():]
                rest_matches = list(re.finditer(r"(?<!\\)(?<!\$)\$\$(?!\$)", rest))

                if len(rest_matches) == 1:
                    # Single opening $$ on this line -> place at column 0
                    in_math_block = True
                    new_lines.append(f"{bq_prefix}{rest.lstrip()}")
                elif len(rest_matches) >= 2:
                    # Opens and closes on same line -> place at column 0
                    m_close = rest_matches[1]
                    math_part = rest[:m_close.end()]
                    trailing = rest[m_close.end():]
                    new_lines.append(f"{bq_prefix}{math_part.lstrip()}")
                    if trailing.strip():
                        new_lines.append(trailing.lstrip())
                else:
                    new_lines.append(f"{bq_prefix}{rest.lstrip()}")

    if collapse_single_line:
        # Collapse blocks of shape:
        # $$
        # formula
        # $$
        # into:
        # $$ formula $$
        collapsed_lines: list[str] = []
        i = 0
        while i < len(new_lines):
            curr_stripped = new_lines[i].strip()
            if (
                curr_stripped == "$$"
                and i + 2 < len(new_lines)
                and new_lines[i + 2].strip() == "$$"
                and "$$" not in new_lines[i + 1]
            ):
                formula = new_lines[i + 1].strip()
                bq_match = re.match(r"^(\s*(?:>\s*)*)", new_lines[i])
                bq = bq_match.group(1).lstrip() if bq_match and ">" in bq_match.group(1) else ""
                collapsed_lines.append(f"{bq}$${formula}$$" if formula.startswith(" ") else f"{bq}$$ {formula} $$")
                i += 3
            else:
                collapsed_lines.append(new_lines[i])
                i += 1
        new_lines = collapsed_lines

    result = "\n".join(new_lines)
    if content.endswith("\n"):
        result += "\n"
    return result, fixed_count


def process_markdown_math(
    content: str,
    fix_brackets: bool = True,
    fix_tables: bool = True,
    fix_line_start: bool = True,
    collapse_single_line: bool = False,
) -> tuple[str, int, int, int]:
    r"""Process a markdown string to validate and fix LaTeX math environments.

    Parameters
    ----------
    content : str
        Input markdown document text.
    fix_brackets : bool, default=True
        Whether to convert '\[' and '\]' to '$$' (or '$' in tables).
    fix_tables : bool, default=True
        Whether to convert '$$' to '$' in tables.
    fix_line_start : bool, default=True
        Whether to place opening '$$' at the beginning of a new line.
    collapse_single_line : bool, default=False
        Whether to collapse single-equation multiline blocks to '$$ formula $$'.

    Returns
    -------
    tuple of (str, int, int, int)
        Transformed markdown content, count of bracket lines modified,
        count of table rows modified, and count of line-start adjustments.
    """
    bracket_fixes = 0
    table_fixes = 0
    line_start_fixes = 0

    if fix_brackets:
        content, bracket_fixes = replace_bracket_math(content)

    if fix_tables:
        content, table_fixes = replace_table_math(content)

    if fix_line_start:
        content, line_start_fixes = fix_display_math_line_start(
            content, collapse_single_line=collapse_single_line
        )

    return content, bracket_fixes, table_fixes, line_start_fixes


def process_file(
    file_path: Path,
    dry_run: bool = False,
    check_only: bool = False,
    fix_brackets: bool = True,
    fix_tables: bool = True,
    fix_line_start: bool = True,
    collapse_single_line: bool = False,
) -> list[MathIssue]:
    r"""Process a single markdown file according to the requested operations.

    Parameters
    ----------
    file_path : Path
        Path to the target markdown file.
    dry_run : bool, default=False
        If True, only display diffs without writing.
    check_only : bool, default=False
        If True, only report detected issues without modifying files.
    fix_brackets : bool, default=True
        Whether to convert bracket math '\[' and '\]' to '$$' or '$'.
    fix_tables : bool, default=True
        Whether to convert table '$$' to '$'.
    fix_line_start : bool, default=True
        Whether to place opening '$$' at beginning of new line with no whitespaces.
    collapse_single_line : bool, default=False
        Whether to collapse single-line multiline blocks to '$$ formula $$'.

    Returns
    -------
    list of MathIssue
        List of all detected issues.
    """
    content = file_path.read_text(encoding="utf-8")
    issues: list[MathIssue] = []

    if fix_brackets:
        issues.extend(check_bracket_math(content))
    if fix_tables:
        issues.extend(check_math_in_tables(content))
    if fix_line_start:
        issues.extend(check_display_math_line_start(content))

    if not issues:
        return []

    if check_only:
        print(f"\n[!] {file_path} ({len(issues)} issues found):")
        for issue in issues:
            print(f"  Line {issue.line_number}: {issue.description}")
        return issues

    transformed, b_fixes, t_fixes, s_fixes = process_markdown_math(
        content,
        fix_brackets=fix_brackets,
        fix_tables=fix_tables,
        fix_line_start=fix_line_start,
        collapse_single_line=collapse_single_line,
    )

    if transformed != content:
        print(
            f"\n[+] {file_path} ("
            f"{b_fixes} bracket math lines, "
            f"{t_fixes} table rows, "
            f"{s_fixes} line-start fixes):"
        )
        if dry_run:
            diff = difflib.unified_diff(
                content.splitlines(keepends=True),
                transformed.splitlines(keepends=True),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            )
            print("".join(diff))
        else:
            file_path.write_text(transformed, encoding="utf-8")
            print("  -> Updated successfully.")

    return issues


def main() -> None:
    """Command-line interface to check and fix math environments in Markdown."""
    cli_parser = argparse.ArgumentParser(
        description="Verify and fix LaTeX math environments in Markdown files (brackets, tables, and display math)."
    )
    cli_parser.add_argument(
        "paths",
        nargs="*",
        default=["docs"],
        help="Files or directories to scan (default: 'docs')",
    )
    cli_parser.add_argument(
        "--check",
        action="store_true",
        help="Check only and report violations without modifying files (exits with code 1 if issues exist)",
    )
    cli_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview unified diffs without modifying files on disk",
    )
    cli_parser.add_argument(
        "--only-brackets",
        action="store_true",
        help="Only transform '\\[ ... \\]' to '$$' or '$' (skip table and line-start formatting)",
    )
    cli_parser.add_argument(
        "--only-tables",
        action="store_true",
        help="Only replace '$$' with '$' inside tables (skip line-start and bracket formatting)",
    )
    cli_parser.add_argument(
        "--only-line-start",
        action="store_true",
        help="Only place opening '$$' at line start (skip bracket and table math conversion)",
    )
    cli_parser.add_argument(
        "--collapse",
        action="store_true",
        help="Collapse single-equation multiline blocks ($$\\nformula\\n$$) into single line ($$ formula $$)",
    )

    args = cli_parser.parse_args()

    any_only = args.only_brackets or args.only_tables or args.only_line_start
    fix_brackets = args.only_brackets or not any_only
    fix_tables = args.only_tables or not any_only
    fix_line_start = args.only_line_start or not any_only

    matched_files: list[Path] = []
    for path_str in args.paths:
        p = Path(path_str)
        if p.is_file() and p.suffix.lower() == ".md":
            matched_files.append(p)
        elif p.is_dir():
            matched_files.extend(p.rglob("*.md"))

    if not matched_files:
        print("No markdown files found to process.")
        return

    total_issues = 0
    modified_files = 0

    print(f"Scanning {len(matched_files)} markdown files...")
    for file_path in matched_files:
        issues = process_file(
            file_path,
            dry_run=args.dry_run,
            check_only=args.check,
            fix_brackets=fix_brackets,
            fix_tables=fix_tables,
            fix_line_start=fix_line_start,
            collapse_single_line=args.collapse,
        )
        if issues:
            total_issues += len(issues)
            modified_files += 1

    if args.check:
        print(f"\nValidation complete: {total_issues} issues found across {modified_files} files.")
        if total_issues > 0:
            raise SystemExit(1)
    else:
        mode_str = "would be modified (dry-run)" if args.dry_run else "modified"
        print(f"\nDone: {modified_files} / {len(matched_files)} files {mode_str} ({total_issues} total issues).")


if __name__ == "__main__":
    main()
