# Repository Scripts & Utilities

This directory contains standalone developer and maintenance utilities for the **Episteme** repository.

---

## Available Scripts

### `convert_callouts.py`

Batch-converts Obsidian / GitHub Flavored Markdown (GFM) callouts to MkDocs & Zensical admonitions.

#### Background & Attribution
Adapted from [`mkdocs-callouts`](https://github.com/sondregronas/mkdocs-callouts) by Sondre Grønås (MIT License). 
While the original package was designed as an in-memory MkDocs runtime hook, this standalone script acts as a static file migration CLI with fixes for CommonMark lazy line wrapping and standard 4-space markdown indentation.

#### Syntax Transformation

| Source (Obsidian / GFM Callouts) | Target (Zensical / MkDocs Admonition) |
|---|---|
| `> [!NOTE]`<br>`> Content` | `!!! note`<br>`    Content` |
| `> [!TIP] Custom Title`<br>`> Content` | `!!! tip "Custom Title"`<br>`    Content` |
| `> [!QUESTION]+ Open Collapsible`<br>`> Content` | `???+ question "Open Collapsible"`<br>`    Content` |
| `> [!WARNING]- Closed Collapsible`<br>`> Content` | `??? warning "Closed Collapsible"`<br>`    Content` |
| `> [!IMPORTANT]` (Obsidian alias)<br>`> Content` | `!!! tip "Important"`<br>`    Content` |
| `> [!CAUTION]` (Obsidian alias)<br>`> Content` | `!!! warning "Caution"`<br>`    Content` |

---

### Usage & Commands

Run using your preferred Python environment or `uv`:

#### 1. Dry Run (Preview Changes Safely)
Prints a unified diff without modifying any files on disk:
```bash
# Preview changes for all docs
python3 scripts/convert_callouts.py docs/ --dry-run

# Preview changes for a single file
python3 scripts/convert_callouts.py docs/concepts/pipeline_architecture.md --dry-run
```

#### 2. Execute Conversion In-Place
Applies the conversion directly to files:
```bash
# Convert all markdown files in docs/
python3 scripts/convert_callouts.py docs/

# Or using uv
uv run python scripts/convert_callouts.py docs/
```

#### 3. CLI Options & Flags

| Flag | Default | Description |
|---|---|---|
| `paths` | `['docs']` | One or more `.md` file paths or directories to scan recursively. |
| `--dry-run` | `False` | Computes changes and displays unified diffs without modifying files. |
| `--title-from-first-bold` | `False` | If a callout has no title, promotes the first bold line (`> **Subtitle:**`) to the admonition title (`!!! note "Subtitle:"`). |
| `--use-tabs` | `False` | Retains literal tab characters (`\t`) instead of converting indentation to standard 4 spaces (`    `). |
| `--no-lazy-continuation` | `False` | Disables automatic indentation of wrapped blockquote lines that lack a leading `>`. |

#### Examples

**Promote bold subtitles to admonition titles:**
```bash
python3 scripts/convert_callouts.py docs/ --title-from-first-bold
```

**Convert specific files only:**
```bash
python3 scripts/convert_callouts.py docs/research/metrics.md docs/concepts/assumptions_limitations.md
```

---

### `format_math_environments.py`

Verifies and standardizes LaTeX math environments (`\[ ... \]`, `$$ ... $$`) across Markdown documentation.

#### Key Functions

1. **Bracket Math Transformation (`fix_brackets`)**:
   Transforms raw LaTeX bracket display math (`\[ ... \]`) to standard Markdown math syntax **before** executing other normalization rules:
   - Inside Markdown table rows: transforms `\[` and `\]` into inline math (`$ ... $`), preventing broken table layout across renderers (KaTeX, MathJax, Zensical).
   - Outside tables: transforms `\[` and `\]` into display math (`$$ ... $$`), allowing downstream column-0 alignment and block-collapsing rules to format them consistently.
2. **Table Math Sanitization (`fix_tables`)**:
   Replaces display math `$$ ... $$` with inline math `$ ... $` inside Markdown table cells. Display math inside table rows frequently breaks Markdown table layout across renderers.
3. **Line-Start Display Math (`fix_line_start`)**:
   Verifies and ensures that every display math environment (`$$ ... $$` or multiline `$$\n...\n$$`) starts at column 0 with **no leading whitespaces** (or blockquote `> ` markers only), stripping any indentation that would cause Markdown parsers to misidentify the equation as an indented code block.

#### Usage & Commands

##### 1. Validation / CI Check Mode
Scans files and exits with code `1` if any issues are detected:
```bash
python3 scripts/format_math_environments.py docs/ --check
```

##### 2. Dry Run (Preview Changes Safely)
Prints unified diffs without modifying files on disk:
```bash
python3 scripts/format_math_environments.py docs/ --dry-run
```

##### 3. Apply Fixes In-Place
```bash
# Fix bracket math, table math, and line-start formatting (multiline format)
python3 scripts/format_math_environments.py docs/

# Collapse single equations to one line ($$ formula $$)
python3 scripts/format_math_environments.py docs/ --collapse

# Only convert LaTeX bracket math (\[ ... \] -> $$ or $)
python3 scripts/format_math_environments.py docs/ --only-brackets

# Only convert table math ($$ -> $)
python3 scripts/format_math_environments.py docs/ --only-tables

# Only fix line-start formatting for display math
python3 scripts/format_math_environments.py docs/ --only-line-start
```

#### CLI Options & Flags

| Flag | Default | Description |
|---|---|---|
| `paths` | `['docs']` | One or more `.md` file paths or directories to scan recursively. |
| `--check` | `False` | Validates files without writing, prints detected issues, and exits with code 1 on failure. |
| `--dry-run` | `False` | Displays unified diffs without modifying files. |
| `--collapse` | `False` | Collapses single-equation multiline blocks into a single line (`$$ formula $$`) with column 0 alignment. |
| `--only-brackets` | `False` | Restricts transformation to converting `\[ ... \]` to `$$` (or `$` in tables). |
| `--only-tables` | `False` | Restricts transformation to converting `$$` to `$` in table rows. |
| `--only-line-start` | `False` | Restricts transformation to placing opening `$$` at line beginnings with no whitespace. |



