"""Test configuration and shared fixtures."""

import ast
import json
import pathlib

import pandas as pd
import pytest


@pytest.fixture
def sample_mixed_markdown() -> str:
    """Sample markdown text with mixed heading styles for testing."""
    return (pathlib.Path(__file__).parent / "fixtures" / "mixed.md").read_text()


@pytest.fixture
def sample_mixed_json() -> dict:
    """Expected JSON output for mixed markdown fixture."""
    with open(pathlib.Path(__file__).parent / "fixtures" / "mixed.json") as f:
        return json.load(f)


@pytest.fixture
def sample_match_markdown() -> str:
    """Sample markdown text for matcher testing."""
    return (pathlib.Path(__file__).parent / "fixtures" / "match.md").read_text()


@pytest.fixture
def sample_match_json() -> dict:
    """Expected JSON output for match markdown fixture."""
    with open(pathlib.Path(__file__).parent / "fixtures" / "match.json") as f:
        return json.load(f)


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Sample DataFrame with markdown content for batch processing tests."""
    return pd.read_csv(pathlib.Path(__file__).parent / "fixtures" / "sample_data.csv")


@pytest.fixture
def sample_dataframe_parsed() -> pd.DataFrame:
    """Expected parsed output for sample_dataframe."""
    path = pathlib.Path(__file__).parent / "fixtures" / "sample_data_parsed.csv"
    df = pd.read_csv(path)

    # Convert string representations of lists back to actual lists
    df["parents"] = df["parents"].apply(ast.literal_eval)
    df["parent_types"] = df["parent_types"].apply(ast.literal_eval)

    return df


@pytest.fixture
def sample_dataframe_match() -> pd.DataFrame:
    """Sample DataFrame with markdown content for batch processing with matcher."""
    return pd.read_csv(
        pathlib.Path(__file__).parent / "fixtures" / "sample_data_match.csv"
    )


@pytest.fixture
def sample_dataframe_match_parsed() -> pd.DataFrame:
    """Expected parsed output for sample_dataframe_match with matcher."""
    path = pathlib.Path(__file__).parent / "fixtures" / "sample_data_match_parsed.csv"
    df = pd.read_csv(path)

    # Convert string representations of lists back to actual lists
    df["parents"] = df["parents"].apply(ast.literal_eval)
    df["parent_types"] = df["parent_types"].apply(ast.literal_eval)
    df["matched_headings"] = df["matched_headings"].apply(ast.literal_eval)
    df["missing_headings"] = df["missing_headings"].apply(ast.literal_eval)

    return df


@pytest.fixture
def expected_json_files() -> dict[str, dict]:
    """Expected JSON output files for batch processing tests."""
    json_dir = pathlib.Path(__file__).parent / "fixtures" / "expected_json"
    result = {}
    for json_file in sorted(json_dir.glob("*.json")):
        with open(json_file) as f:
            result[json_file.name] = json.load(f)
    return result


@pytest.fixture
def expected_tree_files() -> dict[str, str]:
    """Expected tree output files for batch processing tests."""
    tree_dir = pathlib.Path(__file__).parent / "fixtures" / "expected_tree"
    result = {}
    for tree_file in sorted(tree_dir.glob("*.txt")):
        result[tree_file.name] = tree_file.read_text()
    return result
