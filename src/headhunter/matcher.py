"""Heading matcher module for validating and extracting expected headings."""

from typing import Any

from rapidfuzz import fuzz

from headhunter import config as _config
from headhunter import models, utils

logger = _config.get_logger(__name__)


def _find_exact_match_in_range(
    tokens: list[models.Token], expected_heading: str, start_idx: int
) -> tuple[models.Token, int] | None:
    """Finds exact case-insensitive match among heading tokens from start_idx onwards.

    Args:
        tokens: List of tokens to search.
        expected_heading: Heading text to find.
        start_idx: Index to start searching from (inclusive).

    Returns:
        Tuple of (matching_token, token_index) if found, None otherwise.
    """
    expected_lower = expected_heading.lower().strip()
    for idx in range(start_idx, len(tokens)):
        token = tokens[idx]
        if token.type == "heading":
            if token.content.lower().strip() == expected_lower:
                return token, idx
    return None


def _find_next_expected_heading_match(
    tokens: list[models.Token],
    expected_headings: list[str],
    current_expected: str,
    start_idx: int,
) -> int | None:
    """Finds if any subsequent expected heading matches remaining heading tokens.

    Looks ahead in expected_headings list (after current_expected) to see if any of
    those headings match heading tokens in remaining token list.

    Args:
        tokens: List of tokens to search.
        expected_headings: Full list of expected headings.
        current_expected: Current expected heading being processed.
        start_idx: Index to start searching from.

    Returns:
        Index of first heading token that matches a subsequent expected heading,
        or None if no match found.
    """
    current_pos = expected_headings.index(current_expected)

    subsequent_expected = expected_headings[current_pos + 1 :]
    if not subsequent_expected:
        return None

    subsequent_expected_lower = [h.lower().strip() for h in subsequent_expected]

    for idx in range(start_idx, len(tokens)):
        token = tokens[idx]
        if token.type == "heading":
            token_content_lower = token.content.lower().strip()
            if token_content_lower in subsequent_expected_lower:
                return idx

    return None


def _find_best_substring_match(
    line: str, expected_heading: str, expected_lower: str, threshold: int
) -> tuple[str, int, int] | None:
    """Finds the best matching substring in a line for the expected heading.

    Uses rapidfuzz's partial_ratio_alignment to find the substring that best matches
    the expected heading text. For all-caps standalone lines, prefers the full line
    to avoid incorrect inline detection.

    Args:
        line: Line of text to search.
        expected_heading: Expected heading text (original case).
        expected_lower: Expected heading text (lowercase).
        threshold: Minimum fuzzy match score to accept.

    Returns:
        Tuple of (matched_substring, char_start, char_end) if found, None otherwise.
    """
    line_lower = line.lower()
    line_stripped = line.strip()

    if utils.detect_text_case(line_stripped) == "all_caps":
        full_line_score = fuzz.ratio(expected_lower, line_lower.strip())
        if full_line_score >= threshold:
            actual_start = line.find(line_stripped)
            if actual_start != -1:
                actual_end = actual_start + len(line_stripped)
                return line_stripped, actual_start, actual_end

    alignment = fuzz.partial_ratio_alignment(expected_lower, line_lower)

    if alignment is None or alignment.score < threshold:
        return None

    raw_match = line[alignment.dest_start : alignment.dest_end]
    matched_text = raw_match.strip()

    if not matched_text:
        return None

    # Calculate adjusted positions accounting for leading whitespace stripped
    strip_offset = len(raw_match) - len(raw_match.lstrip())
    char_start = alignment.dest_start + strip_offset
    char_end = char_start + len(matched_text)

    if char_start >= 0 and char_end <= len(line):
        return matched_text, char_start, char_end

    return None


def _detect_markers_around_match(
    line: str,
    matched_text: str,
    char_start: int,
    char_end: int,
    config: _config.ParserConfig,
) -> tuple[dict[str, Any], int, int] | tuple[None, int, int]:
    """Detects heading markers using config regex patterns.

    Uses the configured regex patterns (match_hash_pattern, match_asterisk_pattern,
    match_inline_colon_pattern) to detect markers and determine content boundaries.

    Args:
        line: Full line of text.
        matched_text: Matched heading text.
        char_start: Start position of matched text.
        char_end: End position of matched text.
        config: Parser configuration with regex patterns.

    Returns:
        Tuple of (marker_info_dict, adjusted_start, adjusted_end) where marker_info_dict
        contains keys: marker, marker_count, case, original_position. If no markers,
        returns (None, original_start, original_end).
    """
    inline_match = config.match_inline_colon_pattern.search(line)
    if inline_match:
        if inline_match.group(1):  # **Label:** content format
            marker = inline_match.group(1)
            pattern_text_start = inline_match.start(2)
        else:  # **Label**: content format
            marker = inline_match.group(3)
            pattern_text_start = inline_match.start(4)

        pattern_start = inline_match.start()
        pattern_end = inline_match.end()

        if pattern_text_start <= char_start < pattern_end:
            return (
                {
                    "marker": "*",
                    "marker_count": len(marker),
                    "case": utils.detect_text_case(matched_text),
                    "original_position": "inline",
                },
                pattern_start,
                pattern_end,
            )

    hash_match = config.match_hash_pattern.search(line)
    if hash_match:
        pattern_start = hash_match.start()
        pattern_text_start = hash_match.start(2)
        pattern_end = hash_match.end()

        if pattern_text_start <= char_start < pattern_end:
            marker = hash_match.group(1)
            return (
                {
                    "marker": "#",
                    "marker_count": len(marker),
                    "case": utils.detect_text_case(matched_text),
                    "original_position": "standalone",
                },
                pattern_start,
                # This pattern only captures a single word and whitespace after hashes
                # So keep original end to include full matched text
                char_end,
            )

    asterisk_match = config.match_asterisk_pattern.search(line)
    if asterisk_match:
        pattern_start = asterisk_match.start()
        pattern_text_start = asterisk_match.start(2)
        pattern_end = asterisk_match.end()

        if pattern_text_start <= char_start < pattern_end:
            marker = asterisk_match.group(1)
            return (
                {
                    "marker": "*",
                    "marker_count": len(marker),
                    "case": utils.detect_text_case(matched_text),
                    "original_position": "standalone",
                },
                pattern_start,
                pattern_end,
            )

    return None, char_start, char_end


def _fuzzy_match_in_content(
    content_token: models.Token,
    expected_heading: str,
    threshold: int,
    config: _config.ParserConfig,
    warnings: list[str],
) -> tuple[str, int, int, int, dict[str, Any] | None, float] | None:
    """Performs fuzzy matching within content token.

    Uses rapidfuzz.partial_ratio to find best substring match, then extracts exact
    matched substring and detects surrounding markers for metadata.

    Args:
        content_token: Content token to search within.
        expected_heading: Expected heading text.
        threshold: Minimum fuzzy match score.
        config: Parser configuration with relaxed match patterns.
        warnings: List to append warning messages to.

    Returns:
        Tuple of (matched_text, line_offset, char_start, char_end, marker_info,
        confidence) if match found, None otherwise. marker_info is a dictionary with
        keys: marker, marker_count, case, original_position; or None if no pattern
        detected.
    """
    lines = content_token.content.split("\n")
    expected_lower = expected_heading.lower()

    for line_offset, line in enumerate(lines):
        if not line.strip():
            continue

        score = fuzz.partial_ratio(expected_lower, line.lower())

        if score < threshold:
            continue

        substring_result = _find_best_substring_match(
            line, expected_heading, expected_lower, threshold
        )

        if substring_result is None:
            warning_msg = (
                f"Line passed partial_ratio screening (score={score}) but "
                f"substring extraction failed for expected heading '{expected_heading}'"
            )
            logger.warning(warning_msg)
            warnings.append(warning_msg)
            continue

        matched_text, char_start, char_end = substring_result

        marker_result = _detect_markers_around_match(
            line, matched_text, char_start, char_end, config
        )
        marker_info, adjusted_start, adjusted_end = marker_result

        return (
            matched_text,
            line_offset,
            adjusted_start,
            adjusted_end,
            marker_info,
            score,
        )

    return None


def _create_extracted_heading_token(
    content: str,
    line_number: int,
    extraction_position: str,
    marker_info: dict[str, Any] | None,
) -> models.Token:
    """Creates a heading token for an extracted heading with proper metadata.

    Args:
        content: Heading text content.
        line_number: Line number where heading appears.
        extraction_position: "inline" or "standalone".
        marker_info: Dictionary with keys (marker, marker_count, case,
            original_position) or None for markerless headings.

    Returns:
        Token with type="heading" and complete HeadingMetadata.
    """
    if marker_info is not None:
        was_inline = marker_info["original_position"] == "inline"

        metadata = models.HeadingMetadata(
            marker=marker_info["marker"],
            marker_count=marker_info["marker_count"],
            case=marker_info["case"],
            is_inline=was_inline,
            is_extracted=True,
            extraction_position=extraction_position,
        )
    else:
        case = utils.detect_text_case(content)
        was_inline = content.rstrip().endswith(":")

        metadata = models.HeadingMetadata(
            marker=None,
            marker_count=0,
            case=case,
            is_inline=was_inline,
            is_extracted=True,
            extraction_position=extraction_position,
        )

    return models.Token(
        type="heading",
        content=content,
        line_number=line_number,
        metadata=metadata,
    )


def _split_content_token(
    content_token: models.Token,
    matched_heading_text: str,
    match_line_offset: int,
    char_start: int,
    char_end: int,
    marker_info: dict[str, Any] | None,
    config: _config.ParserConfig,
) -> list[models.Token]:
    """Splits content token at matched heading with precise character boundaries.

    Creates pre-content, heading, and post-content tokens with accurate line numbers.
    Handles inline colon headings specially (subsequent lines become siblings).

    Args:
        content_token: Original content token to split.
        matched_heading_text: Extracted heading text.
        match_line_offset: Line offset where match found (0-indexed).
        char_start: Character start position of heading in matched line.
        char_end: Character end position of heading in matched line.
        marker_info: Dictionary with keys (marker, marker_count, case,
            original_position) or None for markerless headings.
        config: Parser configuration.

    Returns:
        List of new tokens (pre-content, heading, post-content tokens).

    Raises:
        ValueError: If match_line_offset is out of bounds.
    """
    lines = content_token.content.split("\n")

    new_tokens: list[models.Token] = []

    matched_line = lines[match_line_offset]
    heading_line_number = content_token.line_number + match_line_offset

    before_text = matched_line[:char_start].strip()
    after_text = matched_line[char_end:].strip()

    extraction_position = "inline" if (before_text or after_text) else "standalone"

    # Create pre-content token (lines before + before_text)
    pre_lines = lines[:match_line_offset]
    if before_text:
        pre_lines.append(before_text)

    if pre_lines:
        pre_content = "\n".join(pre_lines).strip()
        if pre_content:
            new_tokens.append(
                models.Token(
                    type="content",
                    content=pre_content,
                    line_number=content_token.line_number,
                    metadata=None,
                )
            )

    # Create heading token
    heading_token = _create_extracted_heading_token(
        matched_heading_text, heading_line_number, extraction_position, marker_info
    )
    new_tokens.append(heading_token)

    # Create post-content tokens
    # Special handling for inline colon headings
    assert type(heading_token.metadata) is models.HeadingMetadata  # for mypy

    if heading_token.metadata.is_inline:
        if after_text:
            new_tokens.append(
                models.Token(
                    type="content",
                    content=after_text,
                    line_number=heading_line_number,
                    metadata=None,
                )
            )

        subsequent_lines = lines[match_line_offset + 1 :]
        if subsequent_lines:
            subsequent_content = "\n".join(subsequent_lines).strip()
            if subsequent_content:
                # Account for leading blank lines that were stripped
                leading_blank_lines = 0
                for line in subsequent_lines:
                    if line.strip():
                        break
                    leading_blank_lines += 1

                new_tokens.append(
                    models.Token(
                        type="content",
                        content=subsequent_content,
                        line_number=heading_line_number + 1 + leading_blank_lines,
                        metadata=None,
                    )
                )
    else:
        # Regular heading: all post-content becomes children
        post_lines = []
        if after_text:
            post_lines.append(after_text)
        post_lines.extend(lines[match_line_offset + 1 :])

        if post_lines:
            post_content = "\n".join(post_lines).strip()
            if post_content:
                # Calculate base line number
                post_line_number = heading_line_number
                if not after_text and len(post_lines) > 0:
                    post_line_number = heading_line_number + 1

                # Account for leading blank lines that were stripped
                leading_blank_lines = 0
                for line in post_lines:
                    if line.strip():
                        break
                    leading_blank_lines += 1

                new_tokens.append(
                    models.Token(
                        type="content",
                        content=post_content,
                        line_number=post_line_number + leading_blank_lines,
                        metadata=None,
                    )
                )

    return new_tokens


def _find_and_extract_heading(
    tokens: list[models.Token],
    content_tokens_with_indices: list[tuple[int, models.Token]],
    expected_heading: str,
    threshold: int,
    config: _config.ParserConfig,
    warnings: list[str],
) -> tuple[list[models.Token], int, float, int] | None:
    """Searches for and extracts a heading from content tokens using fuzzy matching.

    The function first uses a fuzzy substring scorer (rapidfuzz.partial_ratio) to locate
    the most promising candidate match inside each content token. After a fuzzy
    candidate passes the threshold, it extracts the exact substring and inspects
    surrounding characters to detect markers (like bullets, numbering, separators, or
    punctuation) and to set the heading's line number and token type.

    Args:
        tokens: Full list of tokens.
        content_tokens_with_indices: List of (index, token) tuples for content
            tokens within the search window.
        expected_heading: Heading text to find.
        threshold: Minimum fuzzy match score.
        config: Parser configuration with regex patterns.
        warnings: List to append warning messages to.

    Returns:
        Tuple of (new_tokens, extracted_heading_index, confidence, line_number)
        if match found, None otherwise. extracted_heading_index is the position
        of the newly created heading token in new_tokens.
    """
    for original_idx, token in content_tokens_with_indices:
        match_result = _fuzzy_match_in_content(
            token, expected_heading, threshold, config, warnings
        )

        if match_result is None:
            continue

        (
            matched_text,
            line_offset,
            char_start,
            char_end,
            marker_info,
            confidence,
        ) = match_result

        split_tokens = _split_content_token(
            token, matched_text, line_offset, char_start, char_end, marker_info, config
        )

        new_tokens = tokens[:original_idx] + split_tokens + tokens[original_idx + 1 :]

        # Find the position of the heading token in split_tokens
        # The heading token is the one with type="heading"
        heading_position_in_split = None
        for i, t in enumerate(split_tokens):
            if t.type == "heading":
                heading_position_in_split = i
                break

        assert type(heading_position_in_split) is int  # for mypy
        extracted_heading_idx = original_idx + heading_position_in_split
        heading_line_number = split_tokens[heading_position_in_split].line_number

        return (
            new_tokens,
            extracted_heading_idx,
            confidence,
            heading_line_number,
        )

    return None


def match_headings(
    tokens: list[models.Token],
    expected_headings: list[str],
    threshold: int,
    config: _config.ParserConfig,
) -> tuple[list[models.Token], dict[str, Any], list[str]]:
    """Matches expected headings against parsed tokens with fuzzy extraction.

    This function processes the provided expected_headings sequentially, attempting to
    align each expected heading to the document represented by `tokens`. It uses a
    two-stage strategy for each expected heading:

    1. Exact match stage
       - Starting from the token immediately after the last successfully matched
         heading, the function looks for an existing heading token whose textual content
         matches the expected heading case-insensitively. If found, that heading is
         considered matched (confidence = 100) and the matcher advances past it.

    2. Fuzzy extraction stage
       - If no exact heading token is found, the function determines a constrained
         search window of content tokens in which to attempt fuzzy extraction. This
         window is bounded by the next expected heading that already appears in the
         remaining tokens (if any). This lookahead prevents extracting content across
         boundaries that likely belong to subsequent expected headings.
       - Content tokens in the window are searched in-order in a fuzzy manner
         (find_and_extract_heading) using partial_ratio and substring extraction. When
         an extraction succeeds, the original content token is split into pre-content, a
         new heading token, and post-content. The function then updates the token list
         to keep processing from the newly created heading token onward.

    Args:
        tokens: List of parsed tokens to search.
        expected_headings: List of heading strings to find in document order.
        threshold: Minimum fuzzy match score (0-100) to accept.
        config: Parser configuration with regex patterns.

    Returns:
        Tuple of (updated_tokens, statistics_dict, warnings) where:
        - updated_tokens: Modified token list with extracted headings
        - statistics_dict: Contains match_percentage, missing_headings, matched_headings
        - warnings: List of warning messages
    """
    warnings: list[str] = []

    if not expected_headings:
        warnings.append("Empty expected_headings list provided to matcher")
        logger.warning("Empty expected_headings list, skipping matching")
        return tokens, {}, warnings

    matched_headings: list[dict[str, Any]] = []
    missing_headings: list[str] = []
    current_tokens: list[models.Token] = tokens.copy()
    last_matched_token_index = -1

    for expected_heading in expected_headings:
        search_start_idx = last_matched_token_index + 1

        exact_match_result = _find_exact_match_in_range(
            current_tokens, expected_heading, search_start_idx
        )

        if exact_match_result is not None:
            match_token, match_idx = exact_match_result
            last_matched_token_index = match_idx

            assert type(match_token.metadata) is models.HeadingMetadata  # for mypy

            matched_headings.append(
                {
                    "expected": expected_heading,
                    "matched_text": match_token.content,
                    "extraction_method": "existing_heading",
                    "confidence": 100.0,
                    "line_number": match_token.line_number,
                    "heading_signature": match_token.metadata.signature,
                    "was_extracted": match_token.metadata.is_extracted,
                }
            )
            continue

        next_match_idx = _find_next_expected_heading_match(
            current_tokens, expected_headings, expected_heading, search_start_idx
        )

        if next_match_idx is not None:
            search_window_end = next_match_idx
        else:
            search_window_end = len(current_tokens)

        content_tokens_in_window = []
        for idx in range(search_start_idx, search_window_end):
            if current_tokens[idx].type == "content":
                content_tokens_in_window.append((idx, current_tokens[idx]))

        if not content_tokens_in_window:
            missing_headings.append(expected_heading)
            continue

        extraction_result = _find_and_extract_heading(
            current_tokens,
            content_tokens_in_window,
            expected_heading,
            threshold,
            config,
            warnings,
        )

        if extraction_result is None:
            missing_headings.append(expected_heading)
            continue

        new_tokens, extracted_heading_idx, confidence, line_number = extraction_result

        current_tokens = new_tokens
        last_matched_token_index = extracted_heading_idx

        extracted_token = current_tokens[extracted_heading_idx]
        assert type(extracted_token.metadata) is models.HeadingMetadata  # for mypy
        heading_signature = extracted_token.metadata.signature

        matched_headings.append(
            {
                "expected": expected_heading,
                "matched_text": extracted_token.content,
                "extraction_method": "extracted_from_content",
                "confidence": round(confidence, 2),
                "line_number": line_number,
                "heading_signature": heading_signature,
                "was_extracted": True,
            }
        )

    total_expected = len(expected_headings)
    total_matched = len(matched_headings)
    match_percentage = (
        (total_matched / total_expected * 100) if total_expected > 0 else 0.0
    )

    statistics = {
        "match_percentage": round(match_percentage, 2),
        "missing_headings": missing_headings,
        "matched_headings": matched_headings,
    }

    return current_tokens, statistics, warnings
