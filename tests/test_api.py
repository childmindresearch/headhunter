"""Tests for API entry points."""

import pandas as pd

from headhunter.api import process_batch_df, process_text
from headhunter.models import ParsedBatch, ParsedText


def test_process_text(
    sample_mixed_markdown: str,
) -> None:
    """Test processing of a mixed markdown text."""
    text = sample_mixed_markdown
    metadata = {"source": "unit_test", "id": 123}
    expected_token_count = 18
    expected_heading_count = 10
    expected_content_count = expected_token_count - expected_heading_count

    parsed_text = process_text(
        text,
        metadata=metadata,
    )
    num_headings = sum(1 for t in parsed_text.tokens if t.type == "heading")
    num_content = sum(1 for t in parsed_text.tokens if t.type == "content")

    assert isinstance(parsed_text, ParsedText)
    assert parsed_text.text == text
    assert parsed_text.metadata == metadata
    assert len(parsed_text.tokens) == expected_token_count
    assert len(parsed_text.hierarchy) == expected_token_count
    assert num_headings == expected_heading_count
    assert num_content == expected_content_count


def test_process_batch_df(
    sample_dataframe: pd.DataFrame,
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

    assert isinstance(parsed_batch, ParsedBatch)
    assert len(parsed_batch.documents) == len(df)

    assert parsed_batch.metadata_columns is not None
    for col in metadata_columns:
        assert col in parsed_batch.metadata_columns

    for parsed_text in parsed_batch.documents:
        assert isinstance(parsed_text, ParsedText)
        assert parsed_text.text in df["content"].values
