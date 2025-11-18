"""Data models for markdown parsing and hierarchy representation."""

import dataclasses
import hashlib

import pandas as pd

from headhunter import config as _config

logger = _config.get_logger(__name__)


@dataclasses.dataclass
class Token:
    """Represents a parsed token from a markdown document.

    Attributes:
        type: The type of token ('heading' or 'content').
        content: The text content of the token.
        line_number: The line number where the token appears in the source document.
        metadata: Additional metadata about the token. For headings, includes:
            - marker: The formatting marker ('#' or '*')
            - marker_count: Number of markers (1-6 for '#', 1-3 for '*')
            - case: Text case ('all_caps', 'title_case', 'sentence_case', etc.)
            - position: Heading position ('standalone' or 'inline')
    """

    type: str
    content: str
    line_number: int
    metadata: dict[str, str | int]


@dataclasses.dataclass
class HierarchyContext:
    """Represents hierarchical context for a token.

    This class encapsulates all hierarchy-related information computed
    during the hierarchy analysis phase, separate from the raw token data.

    Attributes:
        token: The Token this context is for.
        level: The computed hierarchical level.
        parents: list of parent heading titles (from root to immediate parent).
        parent_types: list of parent heading type signatures (corresponding to parents).
            Each signature is a string like "#1", "*2-CAPS", "*2-inline", etc.
    """

    token: Token
    level: int
    parents: list[str]
    parent_types: list[str]


@dataclasses.dataclass
class HierarchyState:
    """Tracks state during hierarchy building.

    This class encapsulates all the tracking variables needed to compute
    hierarchical levels for different heading types.

    Attributes:
        all_caps_level: Fixed level for all-caps headings (set on first encounter).
        last_hash_level: Level of the most recent hash heading.
        last_hash_marker_count: Marker count of the most recent hash heading.
        last_asterisk_level: Level of the most recent asterisk heading.
        last_asterisk_marker_count: Marker count of the most recent asterisk heading.
        last_heading_level: Level of the most recent heading (excluding inline).
        previous_heading_was_hash: Whether the previous heading was a hash heading.
    """

    all_caps_level: int | None = None
    last_hash_level: int | None = None
    last_hash_marker_count: int | None = None
    last_asterisk_level: int | None = None
    last_asterisk_marker_count: int | None = None
    last_heading_level: int = 0
    previous_heading_was_hash: bool = False


@dataclasses.dataclass(frozen=True)
class ParsedText:
    """Immutable representation of a parsed markdown document.

    This class stores the complete parsing result including tokens, hierarchy,
    configuration, and any warnings generated during parsing.

    Attributes:
        text: The original markdown text.
        config: The parser configuration used.
        metadata: Additional metadata for the document.
        tokens: List of parsed tokens.
        hierarchy: List of hierarchy contexts for all tokens.
        warnings: List of warning messages generated during parsing.
    """

    text: str
    config: _config.ParserConfig
    metadata: dict[str, object]
    tokens: list[Token]
    hierarchy: list[HierarchyContext]
    warnings: list[str]

    def __post_init__(self) -> None:
        """Auto-generate ID from content hash if not provided in metadata."""
        if "id" not in self.metadata:
            logger.warning("No document ID found. Generating one from content hash.")
            self.metadata["id"] = hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def __repr__(self) -> str:
        """Return a readable string representation."""
        doc_id = self.metadata["id"]
        metadata = {k: v for k, v in self.metadata.items() if k != "id"}
        num_headings = sum(1 for t in self.tokens if t.type == "heading")
        num_content = sum(1 for t in self.tokens if t.type == "content")
        metadata_str = (
            "\n" + "".join(f"    {k}: {v}\n" for k, v in metadata.items())
            if metadata
            else "empty\n"
        )
        warning_str = f"{len(self.warnings)}" if self.warnings else "none"

        return (
            "ParsedText(\n"
            + f"  id: {doc_id}\n"
            + f"  metadata: {metadata_str}"
            + f"  length: {len(self.text)} characters\n"
            + f"  number of headings: {num_headings}\n"
            + f"  number of contents: {num_content}\n"
            + f"  warnings: {warning_str}\n"
            + ")"
        )

    def to_dict(self) -> dict[str, object]:
        """Converts the parsed document to a hierarchical dictionary.

        Returns:
            A nested dictionary representation of the document structure.
        """
        from headhunter import writer

        return writer.to_dict(self.hierarchy, self.metadata)

    def to_json(self, filepath: str, indent: int = 2) -> str:
        """Exports the document to a JSON file.

        Args:
            filepath: Path to the output JSON file.
            indent: Indentation level for pretty printing. Defaults to 2.

        Returns:
            Path to the created file.
        """
        from headhunter import writer

        return writer.to_json_file(self.hierarchy, filepath, self.metadata, indent)

    def to_tree(self, show_line_numbers: bool = True, show_type: bool = True) -> str:
        """Generates an ASCII tree visualization of the document structure.

        Args:
            show_line_numbers: Whether to show line numbers. Defaults to True.
            show_type: Whether to show heading type indicators. Defaults to True.

        Returns:
            ASCII tree representation as a string.
        """
        from headhunter import writer

        # Build metadata heading from document metadata
        metadata_heading = dict(self.metadata) if self.metadata else None
        return writer.to_tree_string(
            self.hierarchy, show_line_numbers, show_type, metadata_heading
        )

    def to_dataframe(self) -> list[dict[str, object]]:
        """Converts the document to row dictionaries.

        Returns:
            List of dictionaries representing content rows with
            hierarchical context.
        """
        from headhunter import writer

        doc_id = str(self.metadata["id"])
        return writer.to_dataframe_rows(self.hierarchy, doc_id, self.metadata)


@dataclasses.dataclass(frozen=True)
class ParsedBatch:
    """Immutable representation of a batch of parsed markdown documents.

    This class stores successfully parsed documents and any errors encountered
    during batch processing.

    Attributes:
        documents: List of successfully parsed ParsedText objects.
        config: The parser configuration used.
        errors: List of error dictionaries for failed documents.
            Each error dict contains: doc_id, error_type, message,
            line_number, traceback, row_index.
        metadata_columns: List of metadata column names that were specified
            during batch processing. Used when converting to dataframe.
    """

    documents: list[ParsedText]
    config: _config.ParserConfig
    errors: list[dict[str, str | int | None]]
    metadata_columns: list[str] | None = None

    def __repr__(self) -> str:
        """Return a readable string representation."""
        total = len(self.documents) + len(self.errors)
        success_rate = f"{len(self.documents) / total:.0%}" if total > 0 else "N/A"
        error_str = f"{len(self.errors)}" if self.errors else "none"

        return (
            "ParsedBatch(\n"
            f"  total documents: {total}\n"
            f"  parsed successfully: {len(self.documents)} ({success_rate})\n"
            f"  errors: {error_str}\n"
            ")"
        )

    def to_dict(self) -> dict[str, object]:
        """Converts all documents to a combined dictionary structure.

        Returns:
            Dictionary with 'documents' key containing list of document dicts,
            and 'errors' key containing error information.
        """
        return {
            "documents": [doc.to_dict() for doc in self.documents],
            "errors": self.errors,
            "total_documents": len(self.documents),
            "total_errors": len(self.errors),
        }

    def to_json(self, output_dir: str, indent: int = 2) -> list[str]:
        """Exports each document to individual JSON files in the output directory.

        Args:
            output_dir: Directory path where JSON files will be saved.
            indent: Indentation level for pretty printing. Defaults to 2.

        Returns:
            List of created file paths.
        """
        from headhunter import writer

        return writer.batch_to_json_files(self.documents, output_dir, indent)

    def to_tree(
        self, output_dir: str, show_line_numbers: bool = True, show_type: bool = True
    ) -> list[str]:
        """Exports each document's tree visualization to individual text files.

        Args:
            output_dir: Directory path where tree files will be saved.
            show_line_numbers: Whether to show line numbers. Defaults to True.
            show_type: Whether to show heading type indicators. Defaults to True.

        Returns:
            List of created file paths.
        """
        from headhunter import writer

        return writer.batch_to_tree_files(
            self.documents, output_dir, show_line_numbers, show_type
        )

    def to_dataframe(self) -> pd.DataFrame:
        """Combines all documents into a single pandas DataFrame.

        Returns:
            DataFrame with all content rows from all documents,
            including any metadata columns specified during batch processing.
        """
        from headhunter import writer

        return writer.batch_to_dataframe(self.documents, self.metadata_columns)


class ParsingError(Exception):
    """Exception raised when a fatal parsing error occurs.

    Attributes:
        message: The error message.
        line_number: The line number where the error occurred (if applicable).
        original_exception: The original exception that caused this
            error (if applicable).
    """

    def __init__(
        self,
        message: str,
        line_number: int | None = None,
        original_exception: Exception | None = None,
    ) -> None:
        """Initializes the ParsingError.

        Args:
            message: The error message.
            line_number: The line number where the error occurred. Defaults to None.
            original_exception: The original exception. Defaults to None.
        """
        self.message = message
        self.line_number = line_number
        self.original_exception = original_exception
        super().__init__(self.message)
