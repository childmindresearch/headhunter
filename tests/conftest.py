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
