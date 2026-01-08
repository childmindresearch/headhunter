"""Utility functions shared across headhunter modules."""

import re


def detect_text_case(text: str) -> str:
    """Detect the case style of a markdown string.

    Args:
        text: A markdown string to analyze

    Returns:
        One of: "all_caps", "all_lowercase", "title_case", "sentence_case", "unknown"
    """
    # Remove markdown formatting to get the actual text content
    # Remove links: [text](url)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    # Remove inline code: `code`
    cleaned = re.sub(r"`[^`]+`", "", cleaned)
    # Remove bold/italic: **text**, *text*, __text__, _text_
    cleaned = re.sub(r"(\*\*|__)(.*?)\1", r"\2", cleaned)
    cleaned = re.sub(r"(\*|_)(.*?)\1", r"\2", cleaned)
    # Remove headers: #
    cleaned = re.sub(r"^#+\s*", "", cleaned)

    # Strip whitespace
    cleaned = cleaned.strip()

    # If empty after cleaning, return unknown
    if not cleaned:
        return "unknown"

    # Extract only alphabetic words
    words = re.findall(r"\b[A-Za-z]+\b", cleaned)

    # If no words found, return unknown
    if not words:
        return "unknown"

    # Check all_caps: all words are uppercase
    if all(word.isupper() for word in words):
        return "all_caps"

    # Check all_lowercase: all words are lowercase
    if all(word.islower() for word in words):
        return "all_lowercase"

    # Check title_case: all words start with uppercase, rest lowercase,
    # except allow short words (up to 4 letters) to be all lowercase
    # like "of", "and", "the", "with", etc.
    if all(word.istitle() if len(word) > 4 else True for word in words):
        return "title_case"

    # Check sentence_case: first word capitalized, rest lowercase
    if len(words) >= 1:
        first_word_correct = words[0][0].isupper() and (
            len(words[0]) == 1 or words[0][1:].islower()
        )
        rest_lowercase = all(word.islower() for word in words[1:])

        if first_word_correct and rest_lowercase:
            return "sentence_case"

    # Everything else is unknown
    return "unknown"
