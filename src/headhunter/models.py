"""Data models for markdown parsing and hierarchy representation."""

import dataclasses
import hashlib

import pandas as pd
from tqdm.auto import tqdm

from headhunter import config as _config

logger = _config.get_logger(__name__)


@dataclasses.dataclass
class HeadingMetadata:
    """Structured metadata for heading tokens.

    Attributes:
        marker: The formatting marker ('#', '*', or None for markerless).
        marker_count: Number of markers (1-6 for '#', 1-3 for '*', 0 for markerless).
        case: Text case pattern ('all_caps', 'title_case', 'sentence_case', etc.).
        is_inline: Whether heading appears inline with colon format (e.g., **Label:**).
        is_extracted: Whether heading was extracted by matcher (vs only parsed).
        extraction_position: Position when extracted ("inline", "standalone", or None).
    """

    marker: str | None
    marker_count: int
    case: str
    is_inline: bool
    is_extracted: bool = False
    extraction_position: str | None = None

    def __post_init__(self) -> None:
        """Validate metadata consistency."""
        if self.marker not in ("#", "*", "column", None):
            msg = f"Invalid marker: {self.marker}"
            logger.error(msg)
            raise ValueError(msg)
        if self.marker == "#" and (self.marker_count < 1 or self.marker_count > 6):
            msg = f"Invalid marker_count for #: {self.marker_count}"
            logger.error(msg)
            raise ValueError(msg)
        if self.marker == "*" and (self.marker_count < 1 or self.marker_count > 3):
            msg = f"Invalid marker_count for *: {self.marker_count}"
            logger.error(msg)
            raise ValueError(msg)
        if self.marker == "column" and self.marker_count != 1:
            msg = f"Invalid marker_count for column: {self.marker_count}"
            logger.error(msg)
            raise ValueError(msg)
        if self.marker is None and self.marker_count != 0:
            msg = f"Invalid marker_count for markerless: {self.marker_count}"
            logger.error(msg)
            raise ValueError(msg)
        if self.case not in (
            "all_caps",
            "all_lowercase",
            "title_case",
            "sentence_case",
            "unknown",
        ):
            msg = f"Invalid case: {self.case}"
            logger.error(msg)
            raise ValueError(msg)
        if self.is_inline and self.marker not in ("*", "column"):
            msg = "Only asterisk or column headings can be inline"
            logger.error(msg)
            raise ValueError(msg)
        if self.is_extracted and self.extraction_position is None:
            msg = "extraction_position required when is_extracted=True"
            logger.error(msg)
            raise ValueError(msg)
        if self.extraction_position not in ("inline", "standalone", None):
            msg = f"Invalid extraction_position: {self.extraction_position}"
            logger.error(msg)
            raise ValueError(msg)

    @property
    def signature(self) -> str:
        """Generate heading type signature.

        Examples:
            - "#1" → hash heading with 1 hash
            - "#2-CAPS" → all-caps hash heading with 2 hashes
            - "*2" → bold heading
            - "*2-inline" → inline bold heading with colon
            - "extracted-inline-#2" → extracted inline hash heading
            - "extracted-inline-*2-inline" → extracted inline bold heading with colon

        Returns:
            A compact string signature representing the heading type.
        """
        if self.marker is None:
            sig = "markerless"
        elif self.marker == "column":
            sig = "column"
        else:
            sig = f"{self.marker}{self.marker_count}"

        if self.case == "all_caps":
            sig += "-CAPS"
        if self.is_inline and self.marker != "column":
            sig += "-inline"

        if self.is_extracted:
            sig = f"extracted-{self.extraction_position}-{sig}"

        return sig

    @property
    def is_hash(self) -> bool:
        """Check if this is a hash heading."""
        return self.marker == "#"

    @property
    def is_asterisk(self) -> bool:
        """Check if this is an asterisk heading."""
        return self.marker == "*"

    @property
    def is_all_caps(self) -> bool:
        """Check if heading is all caps."""
        return self.case == "all_caps"

    def to_dict(self) -> dict[str, str | int | bool | None]:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation of metadata.
        """
        return {
            "marker": self.marker,
            "marker_count": self.marker_count,
            "case": self.case,
            "is_inline": self.is_inline,
            "is_extracted": self.is_extracted,
            "extraction_position": self.extraction_position,
            "signature": self.signature,
        }


@dataclasses.dataclass(frozen=True)
class Token:
    """Represents a parsed token from a markdown document.

    Attributes:
        type: The type of token ('heading' or 'content').
        content: The text content of the token.
        line_number: The line number where the token appears in the source document.
        metadata: Heading metadata (HeadingMetadata for headings, None for content).
    """

    type: str
    content: str
    line_number: int
    metadata: HeadingMetadata | None

    def __post_init__(self) -> None:
        """Validate token consistency."""
        if self.type not in ("heading", "content"):
            msg = f"Invalid token type: {self.type}"
            logger.error(msg)
            raise ValueError(msg)
        if self.type == "heading" and self.metadata is None:
            msg = "Heading tokens must have metadata"
            logger.error(msg)
            raise ValueError(msg)
        if self.type == "content" and self.metadata is not None:
            msg = "Content tokens must not have metadata"
            logger.error(msg)
            raise ValueError(msg)


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
        """Auto-generate ID from content hash if not provided or empty in metadata."""
        existing_id = self.metadata.get("id")
        id_is_empty = (
            existing_id is None
            or pd.isna(existing_id)
            or (isinstance(existing_id, str) and not existing_id.strip())
        )
        if id_is_empty:
            warning_msg = (
                "No valid document ID found. Generating one from content hash."
            )
            self.warnings.append(warning_msg)
            logger.warning(warning_msg)

            # Since structured data has empty text field
            # include content values and row_index to ensure unique IDs
            if self.text:
                hash_source = self.text
            else:
                row_index = self.metadata["row_index"]
                content_values = [t.content for t in self.tokens if t.type == "content"]
                hash_source = f"{row_index}:{'|'.join(content_values)}"

            self.metadata["id"] = hashlib.sha256(
                hash_source.encode("utf-8")
            ).hexdigest()

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
        from headhunter import output

        return output.to_dict(self.hierarchy, self.metadata)

    def to_json(self, filepath: str, indent: int = 2) -> str:
        """Exports the document to a JSON file.

        Args:
            filepath: Path to the output JSON file.
            indent: Indentation level for pretty printing. Defaults to 2.

        Returns:
            Path to the created file.
        """
        from headhunter import output

        return output.to_json_file(self.hierarchy, filepath, self.metadata, indent)

    def to_tree(self, show_line_numbers: bool = True, show_type: bool = True) -> str:
        """Generates an ASCII tree visualization of the document structure.

        Args:
            show_line_numbers: Whether to show line numbers. Defaults to True.
            show_type: Whether to show heading type indicators. Defaults to True.

        Returns:
            ASCII tree representation as a string.
        """
        from headhunter import output

        return output.to_tree_string(
            self.hierarchy, show_line_numbers, show_type, self.metadata
        )

    def to_markdown(self) -> str:
        """Regenerates clean Markdown from the parsed structure.

        Converts the hierarchical structure back into properly formatted Markdown,
        using hash (#) syntax for standard headings and bold (**) format for inline
        colon headings. Includes YAML front matter if metadata exists.

        Returns:
            Regenerated Markdown string.
        """
        from headhunter import output

        return output.to_markdown(self.hierarchy, self.metadata)

    def to_dataframe(self) -> pd.DataFrame:
        """Converts the document to a pandas DataFrame.

        Returns:
            DataFrame where each row is a content token with
            hierarchical context.
        """
        from headhunter import output

        doc_id = str(self.metadata["id"])
        return output.to_dataframe(self.hierarchy, doc_id, self.metadata)

    def match_headings(
        self, expected_headings: list[str], threshold: int = 80
    ) -> "ParsedText":
        """Matches expected headings against document with fuzzy extraction.

        Validates expected headings against parsed tokens. When exact matches fail,
        uses fuzzy matching with pattern detection to extract embedded headings from
        content blocks. Splits content at heading boundaries. Hierarchy is rebuilt after
        all matching completes.

        Args:
            expected_headings: List of heading strings to find in document.
            threshold: Minimum fuzzy match score (0-100). Defaults to 80.

        Returns:
            New ParsedText with updated tokens, hierarchy, and match statistics
            in metadata.
        """
        from headhunter import hierarchy, matcher

        new_warnings = self.warnings.copy()

        updated_tokens, statistics, match_warnings = matcher.match_headings(
            self.tokens, expected_headings, threshold, self.config
        )

        new_warnings.extend(match_warnings)

        hierarchy_builder = hierarchy.HierarchyBuilder()
        new_hierarchy, hierarchy_warnings = hierarchy_builder.build(updated_tokens)

        new_warnings.extend(hierarchy_warnings)

        new_metadata = self.metadata.copy()
        new_metadata.update(statistics)

        return ParsedText(
            text=self.text,
            config=self.config,
            metadata=new_metadata,
            tokens=updated_tokens,
            hierarchy=new_hierarchy,
            warnings=new_warnings,
        )


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
        metadata: Additional metadata for the batch (e.g., match statistics).
        metadata_columns: List of metadata column names that were specified
            during batch processing. Used when converting to dataframe.
    """

    documents: list[ParsedText]
    config: _config.ParserConfig
    errors: list[dict[str, str | int | None]]
    warnings: list[str] = dataclasses.field(default_factory=list)
    metadata: dict[str, object] = dataclasses.field(default_factory=dict)
    metadata_columns: list[str] | None = None

    def __repr__(self) -> str:
        """Return a readable string representation."""
        total = len(self.documents) + len(self.errors)
        success_rate = f"{len(self.documents) / total:.0%}" if total > 0 else "N/A"
        error_str = f"{len(self.errors)}" if self.errors else "none"
        warning_str = f"{len(self.warnings)}" if self.warnings else "none"

        match_info = ""
        if "avg_match_percentage" in self.metadata:
            avg_match = self.metadata["avg_match_percentage"]
            perfect_rate = self.metadata["perfect_match_rate"]
            match_info = (
                f"  avg match percentage: {avg_match:.1f}%\n"
                f"  perfect match rate: {perfect_rate:.0%}\n"
            )

        return (
            "ParsedBatch(\n"
            f"  total documents: {total}\n"
            f"  parsed successfully: {len(self.documents)} ({success_rate})\n"
            f"  errors: {error_str}\n"
            f"  warnings: {warning_str}\n"
            f"{match_info}"
            ")"
        )

    def to_dict(self) -> dict[str, object]:
        """Converts all documents to a combined dictionary structure.

        Returns:
            Dictionary with 'documents' key containing list of document dicts,
            'errors' key containing error information, and 'metadata' with
            batch-level statistics.
        """
        result = {
            "documents": [doc.to_dict() for doc in self.documents],
            "errors": self.errors,
            "warnings": self.warnings,
            "total_documents": len(self.documents),
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
        }

        if self.metadata:
            result["metadata"] = dict(self.metadata)

        return result

    def to_json(self, output_dir: str, indent: int = 2) -> list[str]:
        """Exports each document to individual JSON files in the output directory.

        Args:
            output_dir: Directory path where JSON files will be saved.
            indent: Indentation level for pretty printing. Defaults to 2.

        Returns:
            List of created file paths.
        """
        from headhunter import output

        return output.batch_to_json_files(self.documents, output_dir, indent)

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
        from headhunter import output

        return output.batch_to_tree_files(
            self.documents, output_dir, show_line_numbers, show_type
        )

    def to_markdown(self, output_dir: str) -> list[str]:
        """Exports each document to individual Markdown files in the output directory.

        Args:
            output_dir: Directory path where Markdown files will be saved.

        Returns:
            List of created file paths.
        """
        from headhunter import output

        return output.batch_to_markdown_files(self.documents, output_dir)

    def to_dataframe(self) -> pd.DataFrame:
        """Combines all documents into a single pandas DataFrame.

        Returns:
            DataFrame with all content rows from all documents,
            including any metadata columns specified during batch processing.
            Batch-level metadata (e.g., match statistics) is stored in the
            DataFrame's attrs dictionary.
        """
        from headhunter import output

        df = output.batch_to_dataframe(self.documents, self.metadata_columns)

        if self.metadata:
            df.attrs.update(self.metadata)

        if self.warnings:
            df.attrs["warnings"] = self.warnings
            df.attrs["total_warnings"] = len(self.warnings)

        return df

    def match_headings(
        self, expected_headings: list[str], threshold: int = 80
    ) -> "ParsedBatch":
        """Matches expected headings across all documents in the batch.

        Applies heading matching to each document. Computes and stores batch-level
        statistics including average match percentage, perfect match rate, and
        aggregated missing/matched heading counts.

        Args:
            expected_headings: List of heading strings to find in each document.
            threshold: Minimum fuzzy match score (0-100). Defaults to 80.

        Returns:
            New ParsedBatch with updated documents and batch-level statistics
            in metadata.
        """
        updated_documents: list[ParsedText] = []
        match_percentages: list[float] = []
        all_matched_headings: list[dict] = []
        all_missing_headings: list[str] = []
        all_warnings: list[str] = []

        for doc in tqdm(self.documents, desc="Matching headings"):
            updated_doc = doc.match_headings(expected_headings, threshold)
            updated_documents.append(updated_doc)

            match_pct = updated_doc.metadata["match_percentage"]
            assert type(match_pct) is float
            match_percentages.append(float(match_pct))

            matched = updated_doc.metadata["matched_headings"]
            assert type(matched) is list
            all_matched_headings.extend(matched)

            missing = updated_doc.metadata["missing_headings"]
            assert type(missing) is list
            all_missing_headings.extend(missing)

            doc_id = str(updated_doc.metadata["id"])
            for warning in updated_doc.warnings:
                all_warnings.append(f"[{doc_id}] {warning}")

        avg_match_percentage = sum(match_percentages) / len(match_percentages)
        perfect_matches = sum(1 for pct in match_percentages if pct == 100.0)
        perfect_match_rate = perfect_matches / len(match_percentages)

        batch_metadata = self.metadata.copy()
        batch_metadata.update(
            {
                "avg_match_percentage": round(avg_match_percentage, 2),
                "perfect_match_rate": round(perfect_match_rate, 2),
                "documents_with_perfect_match": perfect_matches,
                "total_matched_headings": len(all_matched_headings),
                "total_missing_headings": len(all_missing_headings),
                "expected_headings_count": len(expected_headings),
                "threshold": threshold,
            }
        )

        return ParsedBatch(
            documents=updated_documents,
            config=self.config,
            errors=self.errors,
            warnings=all_warnings,
            metadata=batch_metadata,
            metadata_columns=self.metadata_columns,
        )


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
