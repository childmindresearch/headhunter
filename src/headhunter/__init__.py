""".. include:: ../../README.md"""  # noqa: D415

from headhunter.api import process_batch_df, process_text
from headhunter.config import ParserConfig
from headhunter.models import ParsedBatch, ParsedText

__all__ = [
    "process_text",
    "process_batch_df",
    "ParserConfig",
    "ParsedText",
    "ParsedBatch",
]
