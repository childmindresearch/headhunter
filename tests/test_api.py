"""Tests for API entry points."""

import pandas as pd

from headhunter.api import process_batch_df, process_text
from headhunter.models import ParsedBatch, ParsedText


def test_process_text(
    sample_mixed_markdown: str,
    sample_mixed_json: dict,
) -> None:
    """Test processing of a mixed markdown text."""
    text = sample_mixed_markdown
    metadata = {"source": "unit_test", "id": 123}

    parsed_text = process_text(
        text,
        metadata=metadata,
    )
    actual_output = parsed_text.to_dict()

    assert type(parsed_text) is ParsedText
    assert actual_output == sample_mixed_json


def test_process_batch_df(
    sample_dataframe: pd.DataFrame,
    sample_dataframe_parsed: pd.DataFrame,
) -> None:
    """Test batch processing of DataFrame."""
    content_column = "content"
    id_column = "doc_id"
    metadata_columns = ["category", "priority"]
    df = sample_dataframe

    parsed_batch = process_batch_df(
        df,
        content_column=content_column,
        id_column=id_column,
        metadata_columns=metadata_columns,
    )

    actual_output = parsed_batch.to_dataframe()

    assert type(parsed_batch) is ParsedBatch
    assert actual_output.equals(sample_dataframe_parsed)


def test_process_text_with_matcher(
    sample_match_markdown: str,
    sample_match_json: dict,
) -> None:
    """Test processing text with heading matcher using match.md fixture."""
    text = sample_match_markdown

    expected_headings = [
        "INITIAL ALL CAPS HEADING",
        "Heading 2",
        "Heading 3",
        "Inline Heading",
        "ANOTHER HEADING WITHOUT MARKESR",
    ]

    parsed_text = process_text(
        text=text,
        metadata={"source": "unit_test", "id": 123},
        expected_headings=expected_headings,
        match_threshold=80,
    )

    actual_output = parsed_text.to_dict()

    assert type(parsed_text) is ParsedText
    assert actual_output == sample_match_json
