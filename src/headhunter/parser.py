"""Tokenization module for parsing markdown text into structured tokens."""

import re

from headhunter import config as _config
from headhunter import models

logger = _config.get_logger(__name__)


class Tokenizer:
    """Tokenizes markdown text into structured tokens.

    This class processes markdown text line by line, identifying headings (hash,
    asterisk, inline with colon, all-caps) and content blocks, creating Token
    objects for each structural element.

    Attributes:
        config: The parser configuration containing regex patterns and settings.
    """

    def __init__(self, config: _config.ParserConfig) -> None:
        """Initializes the Tokenizer.

        Args:
            config: Parser configuration with patterns and settings.
        """
        self.config = config

    @staticmethod
    def _get_heading_signature(metadata: dict[str, str | int]) -> str:
        """Generates a compact string signature for a heading based on its metadata.

        Format: {marker}{count}[-CAPS][-inline]

        Examples:
            - "#1" → hash heading with 1 hash
            - "#2-CAPS" → all-caps hash heading with 2 hashes
            - "*2" → bold heading
            - "*2-inline" → inline bold heading with colon
            - "*2-CAPS" → all-caps bold heading

        Args:
            metadata: The metadata dictionary containing marker, marker_count,
                case, and position.

        Returns:
            A compact string signature representing the heading type.
        """
        marker = metadata["marker"]
        count = metadata["marker_count"]
        case = metadata["case"]
        position = metadata["position"]

        signature = f"{marker}{count}"

        # Add modifiers for special cases
        if case == "all_caps":
            signature += "-CAPS"
        if position == "inline":
            signature += "-inline"

        return signature

    def _is_valid_heading_length(self, content: str) -> bool:
        """Checks if heading content is within the maximum word count limit.

        Args:
            content: The heading content to check.

        Returns:
            True if the content has at most heading_max_words words, False otherwise.
        """
        return len(content.split()) <= self.config.heading_max_words

    def _is_valid_heading(self, line: str) -> bool:
        """Lightweight check if a line is a valid heading (pattern + word count).

        This method is optimized for performance in lookahead scenarios where we only
        need to know IF a line is a heading, without creating Token objects or computing
        metadata like case detection.

        Args:
            line: The line to check.

        Returns:
            True if the line matches any heading pattern AND passes word count
            validation.
        """
        # Check inline heading pattern
        inline_match = self.config.inline_colon_pattern.match(line)
        if inline_match:
            # Extract label from whichever pattern matched
            label = (
                inline_match.group(2)
                if inline_match.group(1)
                else inline_match.group(5)
            ).strip()
            if self._is_valid_heading_length(label):
                return True

        # Check hash heading pattern
        hash_match = self.config.heading_hash_pattern.match(line)
        if hash_match:
            heading_content = hash_match.group(2).strip()
            if self._is_valid_heading_length(heading_content):
                return True

        # Check asterisk heading pattern
        asterisk_match = self.config.heading_asterisk_pattern.match(line)
        if asterisk_match:
            heading_content = asterisk_match.group(2).strip()
            if self._is_valid_heading_length(heading_content):
                return True

        return False

    @staticmethod
    def _detect_case(text: str) -> str:
        """Detects the case pattern of the given text using regex patterns.

        Args:
            text: The text to analyze.

        Returns:
            One of: 'all_caps', 'all_lowercase', 'title_case', 'sentence_case',
            or 'mixed_case'.
        """
        # Return mixed_case if no letters present
        if not re.search(r"[a-zA-Z]", text):
            return "mixed_case"

        # All caps: all letters are uppercase
        if re.match(r"^[^a-z]*$", text) and re.search(r"[A-Z]", text):
            return "all_caps"

        # All lowercase: all letters are lowercase
        if re.match(r"^[^A-Z]*$", text) and re.search(r"[a-z]", text):
            return "all_lowercase"

        # Title case: each word starts with uppercase letter
        # Pattern: word boundaries followed by uppercase, rest lowercase/non-alpha
        if re.match(r"^(\W*[A-Z][a-z]*\W*)+$", text):
            return "title_case"

        # Sentence case: starts with uppercase, rest are lowercase
        # Pattern: optional non-alpha, then uppercase, then only lowercase letters
        if re.match(r"^\W*[A-Z][a-z\W]*$", text) and not re.search(r"[A-Z]", text[1:]):
            return "sentence_case"

        return "mixed_case"

    def _try_parse_inline_heading(
        self, line: str, line_number: int
    ) -> list[models.Token] | None:
        """Attempts to parse a line as an inline heading with colon.

        Inline headings have the format: **Label:** content or **Label**: content
        They create two tokens: a heading token and a content token.

        Args:
            line: The line to parse.
            line_number: The line number in the source document.

        Returns:
            A list containing [heading_token, content_token] if the line matches,
            None otherwise.
        """
        inline_match = self.config.inline_colon_pattern.match(line)
        if not inline_match:
            return None

        # Pattern has two alternatives, check which matched
        if inline_match.group(1):  # **Label:** content format
            marker_count = len(inline_match.group(1))
            label = inline_match.group(2).strip()
            content = inline_match.group(3).strip()
        else:  # **Label**: content format
            marker_count = len(inline_match.group(4))
            label = inline_match.group(5).strip()
            content = inline_match.group(6).strip()

        # Check word count limit
        if not self._is_valid_heading_length(label):
            return None

        case = self._detect_case(label)

        # Create metadata
        metadata: dict[str, str | int] = {
            "marker": "*",
            "marker_count": marker_count,
            "case": case,
            "position": "inline",
        }
        metadata["heading_type"] = self._get_heading_signature(metadata)

        # Create heading token
        heading_token = models.Token(
            type="heading",
            content=label,
            line_number=line_number,
            metadata=metadata,
        )

        # Create content token (always follows inline heading)
        content_token = models.Token(
            type="content",
            content=content,
            line_number=line_number,
            metadata={},
        )

        return [heading_token, content_token]

    def _try_parse_hash_heading(
        self, line: str, line_number: int
    ) -> models.Token | None:
        """Attempts to parse a line as a hash heading.

        Hash headings have the format: # Heading, ## Heading, etc.

        Args:
            line: The line to parse.
            line_number: The line number in the source document.

        Returns:
            A Token if the line matches a hash heading, None otherwise.
        """
        hash_match = self.config.heading_hash_pattern.match(line)
        if not hash_match:
            return None

        marker_count = len(hash_match.group(1))
        heading_content = hash_match.group(2).strip()

        # Check word count limit
        if not self._is_valid_heading_length(heading_content):
            return None

        case = self._detect_case(heading_content)

        # Create metadata
        metadata: dict[str, str | int] = {
            "marker": "#",
            "marker_count": marker_count,
            "case": case,
            "position": "standalone",
        }
        metadata["heading_type"] = self._get_heading_signature(metadata)

        return models.Token(
            type="heading",
            content=heading_content,
            line_number=line_number,
            metadata=metadata,
        )

    def _try_parse_asterisk_heading(
        self, line: str, line_number: int
    ) -> models.Token | None:
        """Attempts to parse a line as an asterisk heading (standalone only).

        Asterisk headings have the format: *Heading*, **Heading**, ***Heading***
        This method only matches standalone headings (not inline with colon).

        Args:
            line: The line to parse.
            line_number: The line number in the source document.

        Returns:
            A Token if the line matches an asterisk heading, None otherwise.
        """
        asterisk_match = self.config.heading_asterisk_pattern.match(line)
        if not asterisk_match:
            return None

        marker_count = len(asterisk_match.group(1))
        heading_content = asterisk_match.group(2).strip()

        # Check word count limit
        if not self._is_valid_heading_length(heading_content):
            return None

        case = self._detect_case(heading_content)

        # Create metadata
        metadata: dict[str, str | int] = {
            "marker": "*",
            "marker_count": marker_count,
            "case": case,
            "position": "standalone",
        }
        metadata["heading_type"] = self._get_heading_signature(metadata)

        return models.Token(
            type="heading",
            content=heading_content,
            line_number=line_number,
            metadata=metadata,
        )

    def tokenize(self, text: str) -> tuple[list[models.Token], list[str]]:
        """Parses markdown text and extracts tokens.

        This method processes the markdown text line by line, identifying:
        - Hash headings (e.g., # Heading, ## Heading)
        - Asterisk headings (e.g., **Bold Heading**, *Italic Heading*)
        - Inline headings with colon (e.g., **Name:** value)
        - All-caps headings (any heading with all uppercase content)
        - Non-heading content

        All headings are assigned type='heading' with metadata distinguishing them:
        - marker: '#' or '*'
        - marker_count: Number of markers
        - case: 'all_caps', 'title_case', 'sentence_case', 'all_lowercase',
          or 'mixed_case'
        - position: 'standalone' or 'inline'

        Args:
            text: The markdown text to parse.

        Returns:
            A tuple of (tokens, warnings) where tokens is a list of Token objects
            and warnings is a list of warning messages.

        Raises:
            ParsingError: If a fatal error occurs that prevents parsing.
        """
        tokens: list[models.Token] = []
        warnings: list[str] = []

        # Check for empty text
        if not text or not text.strip():
            warning_msg = "Empty or whitespace-only text provided"
            logger.debug(warning_msg)
            warnings.append(warning_msg)
            return tokens, warnings

        lines = text.split("\n")
        length = len(lines)
        pos = 0

        try:
            while pos < length:
                line = lines[pos]
                line_number = pos + 1

                # Try to parse as inline heading with colon (highest priority)
                inline_tokens = self._try_parse_inline_heading(line, line_number)
                if inline_tokens:
                    tokens.extend(inline_tokens)
                    pos += 1
                    continue

                # Try to parse as hash heading
                hash_token = self._try_parse_hash_heading(line, line_number)
                if hash_token:
                    tokens.append(hash_token)
                    pos += 1
                    continue

                # Try to parse as asterisk heading (standalone)
                asterisk_token = self._try_parse_asterisk_heading(line, line_number)
                if asterisk_token:
                    tokens.append(asterisk_token)
                    pos += 1
                    continue

                # If we reach here, the line is not a heading (either doesn't match
                # pattern or matches but exceeds word count). Collect it and
                # subsequent non-heading lines.
                non_heading_lines: list[str] = [line]
                pos += 1

                # Continue collecting non-heading lines until we find an actual heading
                while pos < length:
                    line = lines[pos]

                    # Check if the line is a valid heading
                    if self._is_valid_heading(line):
                        break

                    non_heading_lines.append(line)
                    pos += 1

                # Create content token if we have non-heading content
                non_heading_content = "\n".join(non_heading_lines).strip()
                if non_heading_content:
                    token = models.Token(
                        type="content",
                        content=non_heading_content,
                        line_number=line_number,
                        metadata={},
                    )
                    tokens.append(token)

        except Exception as e:
            logger.error(
                f"Fatal error during tokenization at line {pos + 1}: {str(e)}",
                exc_info=True,
            )
            raise models.ParsingError(
                f"Fatal error during tokenization: {str(e)}",
                line_number=pos + 1 if pos < length else None,
                original_exception=e,
            ) from e

        if warnings:
            logger.debug(f"Tokenization completed with {len(warnings)} warning(s)")

        return tokens, warnings
