"""Test configuration and shared fixtures."""

import pathlib

import pandas as pd
import pytest


@pytest.fixture
def sample_mixed_markdown() -> str:
    """Sample markdown text with mixed heading styles for testing."""
    return (pathlib.Path(__file__).parent / "fixtures" / "mixed.md").read_text()


@pytest.fixture
def sample_dataframe() -> pd.DataFrame:
    """Sample DataFrame with markdown content for batch processing tests."""
    return pd.read_csv(pathlib.Path(__file__).parent / "fixtures" / "sample_data.csv")
