"""Tests for utility functions."""

import pytest

from headhunter.utils import detect_text_case


@pytest.mark.parametrize(
    "text,expected",
    [
        ("IDENTIFYING INFORMATION", "all_caps"),
        ("DSM-5 DIAGNOSIS", "all_caps"),
        ("# THIS IS A HEADING", "all_caps"),
        ("ALL CAPS WITH **BOLD**", "all_caps"),
        ("PHQ-9", "all_caps"),
        ("Name", "title_case"),
        ("Date of Birth", "title_case"),
        ("This is also A Title Case String", "title_case"),
        ("Administration for Children's Services (ACS) Involvement", "title_case"),
        ("**Bold Text Here**", "title_case"),
        ("[Link Text](https://example.com)", "title_case"),
        ("this is all lowercase", "all_lowercase"),
        ("this is `code` lowercase", "all_lowercase"),
        ("This is sentence case.", "sentence_case"),
        ("First word capitalized but THEN mixed", "unknown"),
        ("", "unknown"),
        ("123 456", "unknown"),
    ],
)
def test_detect_text_case(text: str, expected: str) -> None:
    """Test markdown string case detection with various inputs."""
    assert detect_text_case(text) == expected
