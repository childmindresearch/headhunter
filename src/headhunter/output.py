"""Output formatting functions for parsed markdown structures."""

import json
import pathlib

import pandas as pd

from headhunter import config as _config
from headhunter import models

logger = _config.get_logger(__name__)


def _pop_stack_to_parent_level(
    stack: list[tuple[int, dict[str, object]]],
    current_level: int,
) -> dict[str, object]:
    """Pops stack until parent level is less than current level.

    Args:
        stack: Stack of (level, section_dict) tuples.
        current_level: Current hierarchy level.

    Returns:
        The parent section dictionary.

    Raises:
        ValueError: If stack is empty.
    """
    if not stack:
        error_msg = "Stack is empty when attempting to pop to parent level."
        logger.error(error_msg)
        raise ValueError(error_msg)

    while len(stack) > 1 and stack[-1][0] >= current_level:
        stack.pop()

    return stack[-1][1]


def to_dict(
    hierarchy: list[models.HierarchyContext],
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    """Converts hierarchy contexts into a nested dictionary structure.

    Args:
        hierarchy: List of HierarchyContext objects representing the
            document structure.
        metadata: Optional metadata to include at root level.

    Returns:
        A hierarchical dictionary where each heading contains its content
        and child sections.
    """
    if not hierarchy:
        logger.warning("Hierarchy is empty; returning only metadata or empty dict.")
        return {**metadata} if metadata else {}

    logger.debug(f"Converting hierarchy with {len(hierarchy)} tokens to dictionary")
    root: dict[str, object] = {**(metadata or {}), "sections": []}

    # Stack: list[(level, section_dict)]
    stack: list[tuple[int, dict[str, object]]] = [(0, root)]

    for ctx in hierarchy:
        token = ctx.token

        if token.type == "heading":
            section = {
                "type": token.type,
                "text": token.content,
                "level": ctx.level,
                "line_number": token.line_number,
                "metadata": token.metadata.to_dict() if token.metadata else None,
                "sections": [],
            }

            parent = _pop_stack_to_parent_level(stack, ctx.level)
            assert type(parent["sections"]) is list  # for mypy
            parent["sections"].append(section)
            stack.append((ctx.level, section))

        elif token.type == "content":
            parent = _pop_stack_to_parent_level(stack, ctx.level)

            content_item = {
                "type": token.type,
                "text": token.content,
                "level": ctx.level,
                "line_number": token.line_number,
            }

            assert type(parent["sections"]) is list  # for mypy
            parent["sections"].append(content_item)

    return root


def to_json_file(
    hierarchy: list[models.HierarchyContext],
    filepath: str | pathlib.Path,
    metadata: dict[str, object] | None = None,
    indent: int = 2,
) -> str:
    """Exports hierarchy to a JSON file.

    Args:
        hierarchy: List of HierarchyContext objects.
        filepath: Path to output JSON file.
        metadata: Optional metadata to include at root level.
        indent: JSON indentation level. Defaults to 2.

    Returns:
        Path to the created file as a string.
    """
    hierarchical_data = to_dict(hierarchy, metadata)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(hierarchical_data, f, indent=indent, ensure_ascii=False)

    logger.debug(f"Exported JSON to {filepath}")
    return str(filepath)


def to_tree_string(
    hierarchy: list[models.HierarchyContext],
    show_line_numbers: bool = True,
    show_type: bool = True,
    metadata_heading: dict[str, object] | None = None,
) -> str:
    """Converts hierarchy to ASCII tree string representation.

    Args:
        hierarchy: List of HierarchyContext objects.
        show_line_numbers: Whether to show line numbers. Defaults to True.
        show_type: Whether to show heading type indicators. Defaults to True.
        metadata_heading: Optional metadata to display at top of tree.

    Returns:
        Tree structure as a string.
    """
    heading_contexts = [ctx for ctx in hierarchy if ctx.token.type == "heading"]

    lines: list[str] = []

    if metadata_heading:
        lines.append("Metadata")
        lines.append("-" * 80)
        for key, value in metadata_heading.items():
            lines.append(f"{key}: {value}")
        lines.append("")

    if not heading_contexts:
        lines.append("No headings found")
        logger.warning("No headings found in hierarchy for tree string output.")
        return "\n".join(lines)

    logger.debug(
        f"Converting hierarchy with {len(heading_contexts)} headings to tree string"
    )

    lines.append("Document Structure")
    lines.append("=" * 80)

    # Track levels and whether they have more siblings
    level_has_more: dict[int, bool] = {}

    for i, ctx in enumerate(heading_contexts):
        heading = ctx.token

        # Determine if this heading has siblings after it at same level
        has_more_siblings = False
        for j in range(i + 1, len(heading_contexts)):
            if heading_contexts[j].level < ctx.level:
                break
            if heading_contexts[j].level == ctx.level:
                has_more_siblings = True
                break

        level_has_more[ctx.level] = has_more_siblings

        prefix = ""
        for level in range(1, ctx.level):
            if level in level_has_more and level_has_more[level]:
                prefix += "│   "
            else:
                prefix += "    "

        if ctx.level > 1:
            if has_more_siblings:
                prefix += "├── "
            else:
                prefix += "└── "

        label = heading.content

        if show_type and heading.metadata:
            type_sig = heading.metadata.signature
            label += f" [{type_sig}]"

        if show_line_numbers:
            label += f" (line {heading.line_number})"

        lines.append(f"{prefix}{label}")

    return "\n".join(lines)


def _ensure_output_directory(output_dir: str | pathlib.Path) -> pathlib.Path:
    """Creates output directory if it doesn't exist.

    Args:
        output_dir: Directory path to create.

    Returns:
        Path object for the directory.
    """
    output_path = pathlib.Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def batch_to_json_files(
    documents: list[models.ParsedText],
    output_dir: str | pathlib.Path,
    indent: int = 2,
) -> list[str]:
    """Exports each document to individual JSON file.

    Args:
        documents: List of ParsedText objects.
        output_dir: Directory where JSON files will be saved.
        indent: JSON indentation level. Defaults to 2.

    Returns:
        List of created file paths.
    """
    output_path = _ensure_output_directory(output_dir)

    logger.debug(f"Exporting {len(documents)} documents to JSON files in {output_dir}")
    created_files: list[str] = []

    for doc in documents:
        doc_id = str(doc.metadata["id"])
        filepath = output_path / f"{doc_id}.json"
        created_file = to_json_file(
            doc.hierarchy,
            filepath,
            metadata=doc.metadata,
            indent=indent,
        )
        created_files.append(created_file)

    return created_files


def batch_to_tree_files(
    documents: list[models.ParsedText],
    output_dir: str | pathlib.Path,
    show_line_numbers: bool = True,
    show_type: bool = True,
) -> list[str]:
    """Exports each document to individual tree text file.

    Args:
        documents: List of ParsedText objects.
        output_dir: Directory where tree files will be saved.
        show_line_numbers: Whether to show line numbers. Defaults to True.
        show_type: Whether to show heading type. Defaults to True.

    Returns:
        List of created file paths.
    """
    output_path = _ensure_output_directory(output_dir)

    logger.debug(f"Exporting {len(documents)} documents to tree files in {output_dir}")
    created_files: list[str] = []

    for doc in documents:
        doc_id = str(doc.metadata["id"])
        filepath = output_path / f"{doc_id}.txt"

        tree_str = to_tree_string(
            doc.hierarchy,
            show_line_numbers=show_line_numbers,
            show_type=show_type,
            metadata_heading=doc.metadata,
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(tree_str)

        created_files.append(str(filepath))

    return created_files


def _to_dataframe_rows(
    hierarchy: list[models.HierarchyContext],
    doc_id: str,
    metadata: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    """Extracts content tokens as DataFrame-compatible row dictionaries.

    Args:
        hierarchy: List of HierarchyContext objects.
        doc_id: Document identifier to include in each row.
        metadata: Optional metadata to include in each row.

    Returns:
        List of dictionaries, one per content token, containing:
        id, metadata fields, start_line, level, length, parents,
        parent_types, content.

    Raises:
        ValueError: If hierarchy is None or doc_id is empty.
    """
    if hierarchy is None:
        error_msg = "hierarchy parameter cannot be None"
        logger.error(error_msg)
        raise ValueError(error_msg)

    if not doc_id or not doc_id.strip():
        error_msg = "doc_id parameter cannot be empty"
        logger.error(error_msg)
        raise ValueError(error_msg)

    rows: list[dict[str, object]] = []

    for ctx in hierarchy:
        if ctx.token.type == "content":
            row: dict[str, object] = {
                "id": doc_id,
                "start_line": ctx.token.line_number,
                "level": ctx.level,
                "length": len(ctx.token.content),
                "parents": ctx.parents,
                "parent_types": ctx.parent_types,
                "content": ctx.token.content,
            }

            if metadata:
                for key, value in metadata.items():
                    row[key] = value

            rows.append(row)

    return rows


def _create_empty_dataframe(
    metadata_columns: list[str] | dict[str, object] | None = None,
) -> pd.DataFrame:
    """Creates empty DataFrame with standard column structure.

    Args:
        metadata_columns: Either a list of metadata column names or a dict
            of metadata to extract keys from.

    Returns:
        Empty DataFrame with proper column structure.
    """
    base_columns = ["id"]
    if metadata_columns:
        if isinstance(metadata_columns, dict):
            base_columns.extend(metadata_columns.keys())
        else:
            base_columns.extend(metadata_columns)
    base_columns.extend(
        ["start_line", "level", "length", "parents", "parent_types", "content"]
    )
    logger.warning(
        "Created empty DataFrame: no content tokens found for DataFrame output."
    )
    return pd.DataFrame(columns=base_columns)


def _order_dataframe_columns(
    df: pd.DataFrame,
    metadata_columns: list[str] | dict[str, object] | None = None,
) -> pd.DataFrame:
    """Orders DataFrame columns consistently.

    Args:
        df: DataFrame to reorder.
        metadata_columns: Either a list of metadata column names or a dict
            of metadata to extract keys from.

    Returns:
        DataFrame with ordered columns.
    """
    column_order = ["id"]
    if metadata_columns:
        metadata_keys = (
            metadata_columns.keys()
            if isinstance(metadata_columns, dict)
            else metadata_columns
        )
        for col in metadata_keys:
            if col in df.columns:
                column_order.append(col)
    column_order.extend(
        ["start_line", "level", "length", "parents", "parent_types", "content"]
    )

    column_order = [c for c in column_order if c in df.columns]
    return df[column_order]


def to_dataframe(
    hierarchy: list[models.HierarchyContext],
    doc_id: str,
    metadata: dict[str, object] | None = None,
) -> pd.DataFrame:
    """Converts a single document to a DataFrame.

    Args:
        hierarchy: List of HierarchyContext objects.
        doc_id: Document identifier to include in each row.
        metadata: Optional metadata to include in each row.

    Returns:
        DataFrame where each row is a content token with hierarchical
        context.
    """
    rows = _to_dataframe_rows(hierarchy, doc_id, metadata)

    if not rows:
        return _create_empty_dataframe(metadata)

    logger.debug(f"Converting document {doc_id} to DataFrame with {len(rows)} rows")

    result_df = pd.DataFrame(rows)
    return _order_dataframe_columns(result_df, metadata)


def batch_to_dataframe(
    documents: list[models.ParsedText],
    metadata_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Converts batch of documents to single DataFrame.

    Args:
        documents: List of ParsedText objects.
        metadata_columns: Optional list of metadata keys to include as
            columns in output DataFrame. Match-related metadata
            (match_percentage, missing_headings, matched_headings) is
            automatically included if present.

    Returns:
        DataFrame where each row is a content token with hierarchical
        context. Multiple rows may have same id if from same document.
    """
    if not documents:
        return _create_empty_dataframe(metadata_columns)

    logger.debug(f"Converting batch of {len(documents)} documents to DataFrame")
    all_rows: list[dict[str, object]] = []

    match_metadata_keys = {"match_percentage", "missing_headings", "matched_headings"}

    for doc in documents:
        doc_id = str(doc.metadata["id"])

        metadata_dict = {}

        if metadata_columns:
            for col in metadata_columns:
                if col in doc.metadata:
                    metadata_dict[col] = doc.metadata[col]

        for key in match_metadata_keys:
            if key in doc.metadata:
                metadata_dict[key] = doc.metadata[key]

        rows = _to_dataframe_rows(doc.hierarchy, doc_id, metadata_dict)
        all_rows.extend(rows)

    if not all_rows:
        return _create_empty_dataframe(metadata_columns)

    result_df = pd.DataFrame(all_rows)

    # Combine metadata_columns with match keys for column ordering
    all_metadata_keys = list(metadata_columns) if metadata_columns else []
    for key in match_metadata_keys:
        if key not in all_metadata_keys and any(
            key in doc.metadata for doc in documents
        ):
            all_metadata_keys.append(key)

    return _order_dataframe_columns(
        result_df, all_metadata_keys if all_metadata_keys else None
    )
