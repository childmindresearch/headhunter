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
- Process single documents or batches from DataFrames
- Export results to DataFrame, JSON, or tree visualizations
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
