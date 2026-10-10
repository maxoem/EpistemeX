"""Convert Obsidian/GitHub style callouts to MkDocs/Zensical admonitions.

Based on CalloutParser from mkdocs-callouts by Sondre Grønås:
https://github.com/sondregronas/mkdocs-callouts

MIT License

Copyright (c) 2022 Sondre Grønås

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path

CALLOUT_BLOCK_REGEX = re.compile(r"^(\s*)((?:> ?)+) *\[!([^\]]*)\]([\-\+]?)(.*)?")
# (1): leading whitespace (all tabs and 4x spaces get reused)
# (2): indents (all leading '>' symbols)
# (3): callout type ([!'capture'] or [!'capture | attribute'] excl. brackets and leading !)
# (4): foldable token (+ or - or <blank>)
# (5): title

CALLOUT_CONTENT_SYNTAX_REGEX = re.compile(r"^(\s*)((?:> ?)+)")
# (1): leading whitespace (all tabs and 4x spaces get reused)
# (2): indents (all leading '>' symbols)

# Allows us to proceed to the next line without adding a blank line in between (title_from_first_bold only)
SKIP_LINE = ["SKIP_LINE"]


class CalloutParser:
    """Class to parse callout blocks from markdown and convert them to mkdocs/zensical supported admonitions.

    Parameters
    ----------
    convert_aliases : bool, default=True
        Whether to convert aliases (e.g. important -> tip, caution -> warning).
    breakless_lists : bool, default=True
        Whether to insert newlines before lists following text.
    title_from_first_bold : bool, default=False
        Whether to extract the first bold line as the admonition title if no title is present.
    indent_spaces : int, default=4
        Number of spaces per indent level (0 or negative to keep literal tabs).
    handle_lazy_continuation : bool, default=True
        Whether to treat unquoted non-empty text following a callout line as a lazy continuation line.
    """

    # From https://help.obsidian.md/How+to/Use+callouts#Types
    aliases = {
        "abstract": ["summary", "tldr"],
        "tip": ["hint", "important"],
        "success": ["check", "done"],
        "question": ["help", "faq"],
        "warning": ["caution", "attention"],
        "failure": ["fail", "missing"],
        "danger": ["error"],
        "quote": ["cite"],
    }
    alias_tuples = [
        (alias, c_type) for c_type, aliases in aliases.items() for alias in aliases
    ]

    def __init__(
        self,
        convert_aliases: bool = True,
        breakless_lists: bool = True,
        title_from_first_bold: bool = False,
        indent_spaces: int = 4,
        handle_lazy_continuation: bool = True,
    ) -> None:
        self.indent_levels: list[int] = list()
        self.convert_aliases: bool = convert_aliases
        self.breakless_lists: bool = breakless_lists
        self.indent_spaces: int = indent_spaces
        self.handle_lazy_continuation: bool = handle_lazy_continuation

        self.text_in_prev_line: bool = False
        self.list_in_prev_line: bool = False
        self.in_codefence: list[int] = list()

        self.title_from_first_bold: bool = title_from_first_bold
        self.look_for_title: bool = False
        self.backup_title: str = ""
        self.temp_block_syntax: str = ""

    def _get_indent(self, indent_level: int, is_block: bool = False) -> str:
        """Return the indent string for the given indent level."""
        indent = ""
        for i in range(indent_level - int(is_block)):
            indent += "\t" if i + 1 in self.indent_levels else "> "

        is_part_of_blockquote = "> " in indent
        if is_part_of_blockquote:
            indent = indent.replace("\t", " " * 4)

        return indent

    def _parse_block_syntax(self, block: re.Match[str]) -> str | list[str]:
        """Convert the callout syntax into mkdocs admonition syntax."""
        whitespace = block.group(1).replace("    ", "\t")
        whitespace = "\t" * whitespace.count("\t")

        indent_level = block.group(2).count(">")
        indent = (
            f"{whitespace}{self._get_indent(indent_level=indent_level, is_block=True)}"
        )

        c_type = block.group(3).lower()
        clean_c_type = c_type.split("|")[0].strip()
        c_type = re.sub(r" *\| *(inline|left) *$", " inline", c_type)
        c_type = re.sub(r" *\| *(inline end|right) *$", " inline end", c_type)
        c_type = re.sub(r" *\|.*", "", c_type)

        if self.convert_aliases:
            c_type = self._convert_aliases(c_type)

        syntax = {"-": "???", "+": "???+"}
        fold_syntax = syntax.get(block.group(4), "!!!")

        title = block.group(5).strip()
        title_exists = bool(title)

        if not title_exists and not c_type.lower().startswith(clean_c_type.lower()):
            title = clean_c_type.capitalize()

        if title in ['""', "''"]:
            title = ' ""'
        elif title:
            title = f' "{title}"'
        else:
            title = ""

        if self.title_from_first_bold and not title_exists:
            if self.look_for_title:
                if self.backup_title:
                    self.temp_block_syntax += f" {self.backup_title}"
                self.temp_block_syntax += "\n"
            else:
                self.temp_block_syntax = ""

            self.look_for_title = True
            self.backup_title = title.strip()
            self.temp_block_syntax += f"{indent}{fold_syntax} {c_type}"
            return SKIP_LINE

        return f"{indent}{fold_syntax} {c_type}{title}"

    @staticmethod
    def _convert_aliases(c_type: str) -> str:
        """Convert aliases to their respective callout type."""
        for alias, identifier in CalloutParser.alias_tuples:
            c_type = re.sub(rf"^{alias}\b", identifier, c_type)
        return c_type

    def _breakless_list_handler(self, line: str) -> str:
        """Insert newline before list if previous line was text."""
        is_list = re.search(r"^\s*(?:[-+*]|\d+\.)\s", line)
        if is_list and self.text_in_prev_line:
            if self.list_in_prev_line:
                return line
            indent = re.search(r"^\t*", line).group()
            line = f"{indent}\n{line}"
        else:
            self.text_in_prev_line = line.strip() != ""
        self.list_in_prev_line = bool(is_list)
        return line

    def _convert_block(self, line: str) -> str | list[str] | None:
        """Match and convert a callout header block."""
        match = re.search(CALLOUT_BLOCK_REGEX, line)
        if match:
            indent_level = match.group(2).count(">")
            if indent_level not in self.indent_levels:
                self.indent_levels.append(indent_level)
            return self._parse_block_syntax(match)
        return None

    def _reset_states(self) -> None:
        """Reset parser state."""
        self.indent_levels = list()
        self.look_for_title = False
        self.backup_title = ""
        self.temp_block_syntax = ""
        self.list_in_prev_line = False
        self.text_in_prev_line = False

    def _convert_content(self, line: str) -> str:
        """Convert callout content by replacing leading '>' with indentation."""
        match = re.search(CALLOUT_CONTENT_SYNTAX_REGEX, line)
        if match and self.indent_levels:
            whitespace = match.group(1).replace("    ", "\t")
            whitespace = "\t" * whitespace.count("\t")

            try:
                while match.group(2).count(">") < self.indent_levels[-1]:
                    self.indent_levels = self.indent_levels[:-1]
            except IndexError:
                self._reset_states()
                return line

            indent = (
                f"{whitespace}{self._get_indent(indent_level=max(self.indent_levels))}"
            )
            line = re.sub(rf"^\s*(?:> ?){{{self.indent_levels[-1]}}}", indent, line)

            if self.title_from_first_bold and self.look_for_title:
                self.look_for_title = False
                block_indent = self.temp_block_syntax.split("\n")[-1].count("\t") + 1
                block_indent = "\t" * block_indent
                title = re.search(block_indent + r"\*\*(.+?)\*\*\s*$", line)
                if title:
                    line = f'{self.temp_block_syntax} "{title.group(1).strip()}"'
                elif self.backup_title:
                    line = f"{self.temp_block_syntax} {self.backup_title}\n{line}"
                else:
                    line = f"{self.temp_block_syntax}\n{line}"

            if self.breakless_lists:
                line = self._breakless_list_handler(line)
        elif self.indent_levels and self.handle_lazy_continuation and line.strip() and not line.strip().startswith(("#", "```", "---")):
            # Lazy continuation line inside a callout block
            indent = self._get_indent(indent_level=max(self.indent_levels))
            line = f"{indent}{line}"
            if self.breakless_lists:
                line = self._breakless_list_handler(line)
        else:
            if self.title_from_first_bold and self.look_for_title:
                if self.backup_title:
                    line = f"{self.temp_block_syntax} {self.backup_title}\n{line}"
                else:
                    line = f"{self.temp_block_syntax}\n{line}"
            self._reset_states()

        return line

    def _toggle_codefence_at_index(self, index: int) -> None:
        """Toggle codefence tracking index."""
        if index != 0:
            index = 1
        if index in self.in_codefence:
            self.in_codefence.remove(index)
        else:
            self.in_codefence.append(index)

    def convert_line(self, line: str) -> str | list[str]:
        """Convert a single line of markdown."""
        if re.match(r"^\s*(?:>\s*)*```", line):
            self._toggle_codefence_at_index(line.index("```"))
        if self.in_codefence and self.indent_levels:
            return self._convert_content(line)
        if self.in_codefence:
            return line
        return self._convert_block(line) or self._convert_content(line)

    def parse(self, markdown: str) -> str:
        """Convert callouts in markdown string to admonitions."""
        self._reset_states()
        if not re.search(r"> *\[!", markdown):
            return markdown

        lines = [self.convert_line(line) for line in markdown.split("\n")]
        if (
            self.title_from_first_bold
            and self.temp_block_syntax
            and self.look_for_title
        ):
            if self.backup_title:
                lines += [f"{self.temp_block_syntax} {self.backup_title}"]
            else:
                lines += [self.temp_block_syntax]

        result = "\n".join([line for line in lines if isinstance(line, str)])

        if self.indent_spaces > 0:
            # Replace tab indentation with 4 spaces for standard markdown formatting
            result_lines = []
            for line in result.split("\n"):
                # Count leading tabs
                tab_count = len(line) - len(line.lstrip("\t"))
                if tab_count > 0:
                    line = (" " * self.indent_spaces * tab_count) + line.lstrip("\t")
                result_lines.append(line)
            result = "\n".join(result_lines)

        return result


def convert_file(file_path: Path, parser: CalloutParser, dry_run: bool = False) -> bool:
    """Convert a single markdown file.

    Parameters
    ----------
    file_path : Path
        Path to markdown file.
    parser : CalloutParser
        Configured CalloutParser instance.
    dry_run : bool, default=False
        If True, only print diff without modifying the file.

    Returns
    -------
    bool
        True if the file was modified / would be modified.
    """
    content = file_path.read_text(encoding="utf-8")
    converted = parser.parse(content)

    if content == converted:
        return False

    print(f"\n[+] {file_path}")
    if dry_run:
        diff = difflib.unified_diff(
            content.splitlines(keepends=True),
            converted.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        print("".join(diff))
    else:
        file_path.write_text(converted, encoding="utf-8")
        print("  -> Updated successfully.")
    return True


def main() -> None:
    """Command-line interface to batch convert markdown callouts."""
    cli_parser = argparse.ArgumentParser(
        description="Convert Obsidian/GFM callouts (> [!note]) to MkDocs/Zensical admonitions (!!! note)"
    )
    cli_parser.add_argument(
        "paths",
        nargs="*",
        default=["docs"],
        help="Files or directories to scan (default: 'docs')",
    )
    cli_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes and print diffs without modifying files",
    )
    cli_parser.add_argument(
        "--title-from-first-bold",
        action="store_true",
        help="Use the first bold text as the admonition title if no title is present",
    )
    cli_parser.add_argument(
        "--use-tabs",
        action="store_true",
        help="Keep literal tab characters instead of converting to 4 spaces",
    )
    cli_parser.add_argument(
        "--no-lazy-continuation",
        action="store_true",
        help="Disable automatic handling of lazy blockquote continuation lines without leading '>'",
    )

    args = cli_parser.parse_args()

    parser = CalloutParser(
        title_from_first_bold=args.title_from_first_bold,
        indent_spaces=0 if args.use_tabs else 4,
        handle_lazy_continuation=not args.no_lazy_continuation,
    )

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

    print(f"Scanning {len(matched_files)} markdown files...")
    modified_count = 0
    for file_path in matched_files:
        if convert_file(file_path, parser, dry_run=args.dry_run):
            modified_count += 1

    mode_str = "would be modified (dry-run)" if args.dry_run else "modified"
    print(f"\nDone: {modified_count} / {len(matched_files)} files {mode_str}.")


if __name__ == "__main__":
    main()
