"""Configuration settings and utilities for markdown parsing."""

import dataclasses
import logging
import re


def get_logger(name: str) -> logging.Logger:
    """Returns a configured logger for the given name.

    Args:
        name: The name for the logger (typically __name__).

    Returns:
        A configured Logger instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


@dataclasses.dataclass(frozen=True)
class ParserConfig:
    """Configuration for markdown parsing.

    Attributes:
        heading_hash_pattern: Regex pattern for hash-style headings
            (e.g., # Heading).
        heading_asterisk_pattern: Regex pattern for asterisk-style headings
            (e.g., **Bold**).
        inline_colon_pattern: Regex pattern for inline headings with colon
            (e.g., **Label:** value).
        heading_max_words: Maximum number of words to consider a line as a heading.
    """

    heading_hash_pattern: re.Pattern[str] = re.compile(r"^(#{1,6})\s*(.*)")
    heading_asterisk_pattern: re.Pattern[str] = re.compile(r"^(\*{1,3})\s*(.*?)\s*\1$")
    inline_colon_pattern: re.Pattern[str] = re.compile(
        r"^(\*{1,3})\s*(.*?):\s*\1\s*(.+)$|^(\*{1,3})\s*(.*?)\s*\4:\s*(.+)$"
    )
    heading_max_words: int = 10

    @classmethod
    def from_dict(cls, config_dict: dict[str, int | str]) -> "ParserConfig":
        """Create a ParserConfig from a dictionary with custom parameters.

        Args:
            config_dict: Dictionary with configuration parameters. Supported keys:
                - heading_max_words (int): Maximum words in a heading
                - heading_hash_pattern (str): Regex pattern for hash headings
                - heading_asterisk_pattern (str): Regex pattern for asterisk headings
                - inline_colon_pattern (str): Regex pattern for inline headings

        Returns:
            ParserConfig instance with custom parameters merged with defaults.
        """
        logger = get_logger(__name__)
        valid_params = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs: dict[str, object] = {}

        for key, value in config_dict.items():
            if key in valid_params:
                if key in [
                    "heading_hash_pattern",
                    "heading_asterisk_pattern",
                    "inline_colon_pattern",
                ] and isinstance(value, str):
                    kwargs[key] = re.compile(value)
                elif key == "heading_max_words" and isinstance(value, int):
                    kwargs[key] = value
            else:
                valid_param_names = ", ".join(sorted(valid_params))
                logger.warning(
                    f"Unknown configuration parameter will be ignored: '{key}'. "
                    f"Valid parameters are: {valid_param_names}"
                )

        return cls(**kwargs)  # type: ignore[arg-type]
