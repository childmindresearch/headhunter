"""Tests for API entry points."""

import json
import pathlib

import pandas as pd
import pytest

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
    expected_json_files: dict[str, dict],
    expected_tree_files: dict[str, str],
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test batch processing of DataFrame."""
    content_column = "content"
    id_column = "doc_id"
    metadata_columns = ["category", "priority"]
    df = sample_dataframe
    json_dir = tmp_path / "json"
    tree_dir = tmp_path / "tree"
    json_dir.mkdir()
    tree_dir.mkdir()

    parsed_batch = process_batch_df(
        df,
        content_column=content_column,
        id_column=id_column,
        metadata_columns=metadata_columns,
        config={"heading_max_words": 7, "random_param": 42},
    )
    actual_dataframe = parsed_batch.to_dataframe()
    json_files = parsed_batch.to_json(str(json_dir))
    tree_files = parsed_batch.to_tree(str(tree_dir))

    assert type(parsed_batch) is ParsedBatch
    assert actual_dataframe.equals(sample_dataframe_parsed)
    assert (
        "Unknown custom configuration parameter(s) will be ignored: 'random_param'. "
        in caplog.text
    )

    assert len(json_files) == len(expected_json_files)
    for json_file_path in json_files:
        filename = pathlib.Path(json_file_path).name
        assert filename in expected_json_files
        with open(json_file_path) as f:
            actual_json = json.load(f)
        assert actual_json == expected_json_files[filename]

    assert len(tree_files) == len(expected_tree_files)
    for tree_file_path in tree_files:
        filename = pathlib.Path(tree_file_path).name
        assert filename in expected_tree_files
        actual_tree = pathlib.Path(tree_file_path).read_text()
        assert actual_tree == expected_tree_files[filename]


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


def test_process_batch_df_with_matcher(
    sample_dataframe_match: pd.DataFrame,
    sample_dataframe_match_parsed: pd.DataFrame,
) -> None:
    """Test batch processing of DataFrame with heading matcher."""
    content_column = "content"
    id_column = "doc_id"
    metadata_columns = ["category", "priority"]
    df = sample_dataframe_match

    expected_headings = [
        "INITIAL ALL CAPS HEADING",
        "Heading 2",
        "Heading 3",
        "Inline Heading",
        "ANOTHER HEADING WITHOUT MARKESR",
    ]

    parsed_batch = process_batch_df(
        df,
        content_column=content_column,
        id_column=id_column,
        metadata_columns=metadata_columns,
        expected_headings=expected_headings,
        match_threshold=80,
    )

    actual_output = parsed_batch.to_dataframe()
    # Reorder expected columns to match actual output for comparison
    actual_output = actual_output[sample_dataframe_match_parsed.columns]

    assert type(parsed_batch) is ParsedBatch
    assert actual_output.equals(sample_dataframe_match_parsed)


def test_to_markdown(
    sample_match_markdown: str,
    expected_markdown_match: str,
) -> None:
    """Test markdown regeneration from parsed structure with matcher."""
    text = sample_match_markdown
    metadata = {"source": "unit_test", "id": 123}

    expected_headings = [
        "INITIAL ALL CAPS HEADING",
        "Heading 2",
        "Heading 3",
        "Inline Heading",
        "ANOTHER HEADING WITHOUT MARKESR",
    ]

    parsed_text = process_text(
        text,
        metadata=metadata,
        expected_headings=expected_headings,
        match_threshold=80,
    )
    regenerated = parsed_text.to_markdown()

    assert regenerated == expected_markdown_match


def test_to_markdown_batch(
    sample_dataframe: pd.DataFrame,
    expected_markdown_files: dict[str, str],
    tmp_path: pathlib.Path,
) -> None:
    """Test markdown regeneration for batch processing."""
    content_column = "content"
    id_column = "doc_id"
    metadata_columns = ["category", "priority"]
    output_dir = tmp_path / "markdown_output"

    parsed_batch = process_batch_df(
        sample_dataframe,
        content_column=content_column,
        id_column=id_column,
        metadata_columns=metadata_columns,
    )
    created_files = parsed_batch.to_markdown(str(output_dir))

    assert isinstance(created_files, list)
    assert len(created_files) == len(sample_dataframe)

    for filepath in created_files:
        assert pathlib.Path(filepath).exists()
        assert pathlib.Path(filepath).stem in expected_markdown_files

        with open(filepath, "r", encoding="utf-8") as f:
            markdown = f.read()
        assert markdown == expected_markdown_files[pathlib.Path(filepath).stem]
