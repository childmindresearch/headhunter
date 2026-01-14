"""Public API for markdown parsing and batch processing."""

import traceback

import pandas as pd
from tqdm.auto import tqdm

from headhunter import config as _config
from headhunter import hierarchy, models, parser

logger = _config.get_logger(__name__)


def process_text(
    text: str,
    config: _config.ParserConfig | dict[str, int | str] | None = None,
    metadata: dict[str, object] | None = None,
    expected_headings: list[str] | None = None,
    match_threshold: int = 80,
) -> models.ParsedText:
    """Processes a single markdown text string.

    Args:
        text: The markdown text to parse.
        config: Parser configuration. Can be a ParserConfig object or a dictionary of
            configuration parameters. If None, uses default configuration.
        metadata: Optional metadata to attach to the parsed document.
        expected_headings: Optional list of expected heading strings to match. If
            provided, performs fuzzy matching and extraction.
        match_threshold: Minimum fuzzy match score (0-100) for heading matching.
            Defaults to 80. Only used if expected_headings is provided.

    Returns:
        ParsedText object containing tokens, hierarchy, and warnings.

    Raises:
        ParsingError: If a fatal parsing error occurs.
    """
    if config is None:
        config = _config.ParserConfig()
    elif isinstance(config, dict):
        config = _config.ParserConfig.from_dict(config)

    if metadata is None:
        metadata = {}

    try:
        tokenizer = parser.Tokenizer(config)
        tokens, tokenizer_warnings = tokenizer.tokenize(text)

        hierarchy_builder = hierarchy.HierarchyBuilder()
        hierarchies, hierarchy_warnings = hierarchy_builder.build(tokens)

        all_warnings = tokenizer_warnings + hierarchy_warnings

        parsed_text = models.ParsedText(
            text=text,
            config=config,
            metadata=metadata,
            tokens=tokens,
            hierarchy=hierarchies,
            warnings=all_warnings,
        )

        if expected_headings:
            parsed_text = parsed_text.match_headings(expected_headings, match_threshold)

        return parsed_text

    except Exception as e:
        # Wrap in ParsingError - traceback will be captured by caller
        logger.error(f"Fatal error during parsing: {str(e)}", exc_info=True)
        raise models.ParsingError(
            message=f"Fatal error during parsing: {str(e)}",
            line_number=None,
            original_exception=e,
        ) from e


def process_batch_df(
    df: pd.DataFrame,
    content_column: str = "content",
    id_column: str | None = None,
    metadata_columns: list[str] | None = None,
    config: _config.ParserConfig | dict[str, int | str] | None = None,
    expected_headings: list[str] | None = None,
    match_threshold: int = 80,
) -> models.ParsedBatch:
    """Processes a batch of markdown documents from a DataFrame.

    Args:
        df: Input DataFrame with markdown content.
        content_column: Name of column containing markdown text. Defaults to 'content'.
        id_column: Name of column to use as document ID. If None, generates hash from
            content. Defaults to None.
        metadata_columns: List of additional column names to include as document
            metadata. Defaults to None.
        config: Parser configuration. Can be a ParserConfig object or a dictionary of
            configuration parameters. If None, uses default configuration.
        expected_headings: Optional list of expected heading strings to match across all
            documents. If provided, performs fuzzy matching.
        match_threshold: Minimum fuzzy match score (0-100) for heading matching.
            Defaults to 80. Only used if expected_headings is provided.

    Returns:
        ParsedBatch object containing successfully parsed documents and any errors
        encountered. Use the object's methods to export:
        - batch.to_dataframe() for pandas DataFrame
        - batch.to_json(output_dir) for JSON files
        - batch.to_tree(output_dir) for tree visualizations

    Raises:
        ValueError: If required columns don't exist in DataFrame.
    """
    if content_column not in df.columns:
        raise ValueError(
            f"Column '{content_column}' not found in dataframe. "
            f"Available columns: {list(df.columns)}"
        )

    if id_column is not None and id_column not in df.columns:
        raise ValueError(
            f"Column '{id_column}' not found in dataframe. "
            f"Available columns: {list(df.columns)}"
        )

    if metadata_columns is not None:
        missing_columns = [col for col in metadata_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(
                f"Metadata columns {missing_columns} not found. "
                f"Available columns: {list(df.columns)}"
            )

    if config is None:
        config = _config.ParserConfig()
    elif isinstance(config, dict):
        config = _config.ParserConfig.from_dict(config)

    logger.info(f"Starting batch processing of {len(df)} documents")

    documents: list[models.ParsedText] = []
    errors: list[dict[str, str | int | None]] = []

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Parsing documents"):
        doc_metadata = {"row_index": idx}
        if id_column is not None:
            doc_metadata["id"] = row[id_column]
        if metadata_columns is not None:
            for col in metadata_columns:
                doc_metadata[col] = row[col]

        try:
            parsed_doc = process_text(
                text=row[content_column],
                config=config,
                metadata=doc_metadata,
            )
            documents.append(parsed_doc)

        except models.ParsingError as e:
            doc_id = doc_metadata["id"]
            logger.warning(f"Parsing error for doc_id {doc_id} at row {idx}: {str(e)}")
            tb = traceback.format_exc()
            error_dict = {
                "doc_id": doc_id,
                "row_index": idx,
                "error_type": type(e).__name__,
                "message": str(e),
                "line_number": e.line_number,
                "traceback": tb,
            }
            errors.append(error_dict)

        except Exception as e:
            # Unexpected error - still collect it
            doc_id = doc_metadata["id"]
            logger.error(f"Unexpected error for doc_id {doc_id} at row {idx}: {str(e)}")
            tb = traceback.format_exc()
            error_dict = {
                "doc_id": doc_id,
                "row_index": idx,
                "error_type": type(e).__name__,
                "message": str(e),
                "line_number": None,
                "traceback": tb,
            }
            errors.append(error_dict)

    all_warnings: list[str] = []
    for doc in documents:
        doc_id = str(doc.metadata["id"])
        for warning in doc.warnings:
            all_warnings.append(f"[{doc_id}] {warning}")

    batch = models.ParsedBatch(
        documents=documents,
        config=config,
        errors=errors,
        warnings=all_warnings,
        metadata_columns=metadata_columns,
    )

    if expected_headings:
        batch = batch.match_headings(expected_headings, match_threshold)

    logger.info(
        f"Batch processing complete: {len(documents)} successful, {len(errors)} errors"
    )

    return batch
