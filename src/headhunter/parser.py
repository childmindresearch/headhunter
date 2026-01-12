"""Tokenization module for parsing markdown text into structured tokens."""

from headhunter import config as _config
from headhunter import models, utils

logger = _config.get_logger(__name__)


class Tokenizer:
    """Tokenizes markdown text into structured tokens.

    This class processes markdown text line by line, identifying headings (hash,
    asterisk, inline with colon, all-caps) and content blocks, creating Token objects
    for each structural element.

    Attributes:
        config: The parser configuration containing regex patterns and settings.
    """

    def __init__(self, config: _config.ParserConfig) -> None:
        """Initializes the Tokenizer.

        Args:
            config: Parser configuration with patterns and settings.
        """
        self.config = config

    def _is_valid_heading_length(self, content: str) -> bool:
        """Checks if heading content is within the maximum word count limit.

        Args:
            content: The heading content to check.

        Returns:
            True if the content has at most heading_max_words words.
        """
        return len(content.split()) <= self.config.heading_max_words

    def _is_valid_heading(self, line: str) -> bool:
        """Lightweight check if a line is a valid heading (pattern + word count).

        This method is used in lookahead scenarios where we only need to know IF a line
        is a heading, without creating Token objects or computing metadata like case
        detection or marker count.

        Args:
            line: The line to check.

        Returns:
            True if the line matches any heading pattern AND passes word count
            validation.
        """
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

        hash_match = self.config.heading_hash_pattern.match(line)
        if hash_match:
            heading_content = hash_match.group(2).strip()
            if self._is_valid_heading_length(heading_content):
                return True

        asterisk_match = self.config.heading_asterisk_pattern.match(line)
        if asterisk_match:
            heading_content = asterisk_match.group(2).strip()
            if self._is_valid_heading_length(heading_content):
                return True

        return False

    def _try_parse_inline_heading(
        self, line: str, line_number: int
    ) -> list[models.Token] | None:
        """Attempts to parse a line as an inline heading with colon.

        Inline headings have the format: **Label:** content or **Label**: content. Two
        tokens are created: a heading token and a content token.

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

        if inline_match.group(1):  # **Label:** content format
            marker_count = len(inline_match.group(1))
            label = inline_match.group(2).strip()
            content = inline_match.group(3).strip()
        else:  # **Label**: content format
            marker_count = len(inline_match.group(4))
            label = inline_match.group(5).strip()
            content = inline_match.group(6).strip()

        if not self._is_valid_heading_length(label):
            return None

        case = utils.detect_text_case(label)

        metadata = models.HeadingMetadata(
            marker="*",
            marker_count=marker_count,
            case=case,
            is_inline=True,
            is_extracted=False,
            extraction_position=None,
        )

        heading_token = models.Token(
            type="heading",
            content=label,
            line_number=line_number,
            metadata=metadata,
        )

        content_token = models.Token(
            type="content",
            content=content,
            line_number=line_number,
            metadata=None,
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

        if not self._is_valid_heading_length(heading_content):
            return None

        case = utils.detect_text_case(heading_content)

        metadata = models.HeadingMetadata(
            marker="#",
            marker_count=marker_count,
            case=case,
            is_inline=False,
            is_extracted=False,
            extraction_position=None,
        )

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

        Asterisk headings have the format: *Heading*, **Heading**, ***Heading***. This
        method only matches standalone headings (not inline with colon).

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

        if not self._is_valid_heading_length(heading_content):
            return None

        case = utils.detect_text_case(heading_content)

        metadata = models.HeadingMetadata(
            marker="*",
            marker_count=marker_count,
            case=case,
            is_inline=False,
            is_extracted=False,
            extraction_position=None,
        )

        return models.Token(
            type="heading",
            content=heading_content,
            line_number=line_number,
            metadata=metadata,
        )

    def tokenize(self, text: str) -> tuple[list[models.Token], list[str]]:
        """Parses markdown text and extracts tokens.

        This method processes the markdown text line by line, identifying headings as:
        - Inline headings with colon (e.g., **Name:** value)
        - Hash headings (e.g., # Heading, ## Heading)
        - Asterisk headings (e.g., **Bold Heading**, *Italic Heading*)
        - All-caps headings (any heading format with all uppercase content)

        The rest of the text in between headings are treated as content blocks.

        All headings are assigned type='heading' with HeadingMetadata objects
        containing:
        - marker: '#', '*', or None (for markerless)
        - marker_count: Number of markers
        - case: 'all_caps', 'title_case', 'sentence_case', 'all_lowercase' or 'unknown'
        - is_inline: Whether heading appears inline with colon
        - is_extracted: Whether heading was extracted by matcher
        - extraction_position: Position when extracted ('inline', 'standalone', or None)

        Args:
            text: The markdown text to parse.

        Returns:
            A tuple of (tokens, warnings) where tokens is a list of Token objects and
            warnings is a list of warning messages.

        Raises:
            ParsingError: If a fatal error occurs that prevents parsing.
        """
        tokens: list[models.Token] = []
        warnings: list[str] = []

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

                inline_tokens = self._try_parse_inline_heading(line, line_number)
                if inline_tokens:
                    tokens.extend(inline_tokens)
                    pos += 1
                    continue

                hash_token = self._try_parse_hash_heading(line, line_number)
                if hash_token:
                    tokens.append(hash_token)
                    pos += 1
                    continue

                asterisk_token = self._try_parse_asterisk_heading(line, line_number)
                if asterisk_token:
                    tokens.append(asterisk_token)
                    pos += 1
                    continue

                # If we reach here, the line is not a heading (either doesn't match
                # pattern or matches but exceeds word count). Collect it and subsequent
                # non-heading lines.
                non_heading_lines: list[str] = [line]
                pos += 1

                while pos < length:
                    line = lines[pos]

                    if self._is_valid_heading(line):
                        break

                    non_heading_lines.append(line)
                    pos += 1

                non_heading_content = "\n".join(non_heading_lines).strip()
                if non_heading_content:
                    # Calculate line number accounting for stripped leading lines
                    leading_blank_lines = 0
                    for line in non_heading_lines:
                        if line.strip():
                            break
                        leading_blank_lines += 1

                    adjusted_line_number = line_number + leading_blank_lines

                    token = models.Token(
                        type="content",
                        content=non_heading_content,
                        line_number=adjusted_line_number,
                        metadata=None,
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
