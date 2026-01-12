# headhunter

[![Build](https://github.com/childmindresearch/headhunter/actions/workflows/test.yaml/badge.svg?branch=main)](https://github.com/childmindresearch/headhunter/actions/workflows/test.yaml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/childmindresearch/headhunter/branch/main/graph/badge.svg?token=22HWWFWPW5)](https://codecov.io/gh/childmindresearch/headhunter)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![stability-experimental](https://img.shields.io/badge/stability-experimental-orange.svg)
[![LGPL--2.1 License](https://img.shields.io/badge/license-LGPL--2.1-blue.svg)](https://github.com/childmindresearch/headhunter/blob/main/LICENSE)
[![pages](https://img.shields.io/badge/api-docs-blue)](https://childmindresearch.github.io/headhunter)

A parser for extracting headings and hierarchical structure from Markdown files.

## Features

- Parse multiple heading formats (hash `#`, asterisk `**`, inline with colon, all-caps)
- Build hierarchical structure from headings
- Fuzzy heading matching to extract expected headings from improperly formatted documents, even with typos or spelling variations
- Process single documents or batches from DataFrames
- Export results to DataFrame, JSON, tree visualizations or regenerated clean Markdown
- Configurable parsing rules and word limits

## Installation

Get the newest development version via:

```sh
pip install git+https://github.com/childmindresearch/headhunter
```

## Quick start

**Process a single markdown document:**

```python
import headhunter

# Process markdown text
# This returns a ParsedText object that contains parsed tokens,
# hierarchy, and methods to export/view the results.
parsed_result = headhunter.process_text(
    "# Title\n"
    "## Subtitle\n"
    "Content here"
)

# Export results
parsed_result.to_json("output.json")

# Print tree visualization
print(parsed_result.to_tree())

# Regenerate clean markdown from parsed structure
regenerated_md = parsed_result.to_markdown()
print(regenerated_md)

# View results in a pandas DataFrame
df_parsed = parsed_result.to_dataframe()
print(df_parsed)
```

**Process a batch of documents:**

```python
import pandas as pd
import headhunter

# DataFrame with markdown content
df = pd.DataFrame(
    {
        "doc_id": ["doc1", "doc2"],
        "content": [
            (
                "# Document 1\n\n"
                "This is the first document with some content.\n\n"
                "## Section 1.1\n\n"
                "More details here."
            ),
            (
                "**Document 2**\n\n"
                "**Document type**: Markdown\n\n"
                "A document with asterisk formatting.\n\n"
                "***Subsection***\n\n"
                "Second document with different heading hierarchy.\n\n"
                "*Deeper Subsection*\n\n"
                "Content under deeper subsection."
                "***Another Subsection***\n\n"
                "This should be at the same level as previous subsection."
            ),
        ],
        "category": ["A", "B"],
        "priority": [1, 2],
    }
)

# Process batch
# This returns a ParsedBatch object that contains a list of ParsedText objects
# for each document in the batch, along with methods to export/view the results.
parsed_batch = headhunter.process_batch_df(
    df=df,
    content_column="content",
    id_column="doc_id",
    metadata_columns=["category", "priority"],
    config={"heading_max_words": 7},
)

# View results in a pandas DataFrame
df_parsed = parsed_batch.to_dataframe()
print(df_parsed)

# Export each file's hierarchy to JSON
parsed_batch.to_json("json_outputs/")

# Export each file's tree visualization to text files
parsed_batch.to_tree("tree_outputs/")

# Export parsed data to a CSV file
df_parsed.to_csv("parsed_data.csv")
```

**Extract headings from improperly formatted documents:**

```python
import headhunter

# Document where headings are embedded inline, lack proper formatting or have typos
messy_doc = """
This document has ## Heading 1 embedded in text without line breaks.
Then we have **heading 2** in bold but inline.
**Inline Haedign:** with content on the same line.
"""

# Specify expected headings to extract via fuzzy matching
parsed = headhunter.process_text(
    text=messy_doc,
    expected_headings=["Heading 1", "heading 2", "Inline Heading"],
    match_threshold=80  # 0-100, higher = stricter matching
)

# Match statistics are added to metadata
print(parsed.metadata)  # includes: matched_count, expected_count, match_percentage
```

## How Hierarchy is Built

`headhunter` recognizes different heading styles in Markdown and builds a hierarchical structure by assigning levels to each heading. The following rules govern this process:

### Basic Principles

- **Headings create structure**: Each heading creates a new section in the document's outline
- **Content follows headings**: Regular text is always nested under its nearest heading above
- **First heading starts at level 1**: The first heading in a document becomes the top level

### Rules for Different Heading Types

#### Hash Headings (`#`, `##`, `###`)

These work as expected in standard Markdown:

- More `#` symbols = deeper in the hierarchy
- `# Title` → level 1
- `## Subtitle` → level 2
- `### Sub-subtitle` → level 3

The level increases or decreases based on how many more or fewer `#` symbols are present compared to the previous hash heading.

#### Bold and Italic Headings (`**text**`, `*text*`, `***text***`)

These follow a specific hierarchy from highest to lowest:

1. `**Bold text**` (2 asterisks) = highest level
2. `***Bold and italic***` (3 asterisks) = middle level
3. `*Italic text*` (1 asterisk) = lowest level

When switching between these styles, the level adjusts by just one step up or down:

- Going from bold (`**`) to italic (`*`) moves one level deeper
- Going from italic (`*`) to bold (`**`) moves one level shallower
- Using the same style consecutively keeps the same level

#### ALL CAPS HEADINGS

When a heading with hash (`#`) or asterisk (`**`) markers is written in ALL CAPITAL LETTERS, special rules apply:

- The first ALL CAPS heading sets its level based on what came before it
- Every subsequent ALL CAPS heading uses that same level (they are treated as peers)

Examples:

- `# ALL CAPS HEADING` - Valid heading (hash marker with ALL CAPS text)
- `**ALL CAPS HEADING**` - Valid heading (asterisk marker with ALL CAPS text)
- `ALL CAPS HEADING` - Not a heading (no marker, treated as content)

#### Inline Headings (with colons)

When a heading ends with a colon (like `**Name:** Jane Doe`), it works differently:

- The heading itself goes one level deeper than the previous heading
- The content immediately after it is always treated as the deepest level
- After that content, we return to the normal hierarchy

### Mixed Heading Styles

Different heading styles can be mixed in the same document. When switching from one style to another, the new heading typically goes one level deeper than the previous one. However, the specific rules for each style (described above) still apply.

## Fuzzy Heading Matching

When documents have inconsistent formatting, such as headings embedded inline within text, missing markdown markers, or improper line breaks, `headhunter` can use fuzzy matching to extract expected headings.

**How fuzzy matching works:**

Provide a list of `expected_headings` to `process_text()` or `process_batch_df()`. The matcher will:

1. **Search**: Use fuzzy string matching ([RapidFuzz](https://github.com/maxbachmann/RapidFuzz)) to find heading text within content, even with spelling variations or case differences
2. **Extract**: Identify the best matching substring and detect surrounding markers (`#`, `**`, `*`, `:`)
3. **Split**: Break up content tokens at heading boundaries
4. **Rebuild**: Reconstruct the document hierarchy with extracted headings in their proper positions

**Parameters:**

- `expected_headings`: List of heading strings to find (case-insensitive)
- `match_threshold`: Minimum similarity score 0-100 (default: 80)
  - 80-100: Strict matching, reduces false positives
  - 60-79: Moderate matching, allows more variation
  - Below 60: Lenient matching, may produce unexpected matches

## Markdown Regeneration

After parsing a document, `headhunter` can regenerate clean, standardized Markdown from the parsed structure. This is useful for:

- **Cleaning up messy documents**: Convert inconsistent formatting into standard Markdown
- **Standardizing format**: Make certain all documents use the same heading style
- **Post-processing extracted headings**: Apply fuzzy matching to extract headings, then export the cleaned result

**How regeneration works:**

The `to_markdown()` method converts the parsed hierarchical structure back into Markdown:

- **Standard headings**: Converted to hash format (`#`, `##`, `###`, etc.) based on hierarchical level
- **Inline headings**: Preserved as bold format with colon (`**Heading:** content`)
- **YAML front matter**: Metadata is included as YAML front matter at the top of the document
- **Consistent spacing**: Single blank lines between sections for readability
- **Case preservation**: Original text case is maintained (including ALL CAPS)
