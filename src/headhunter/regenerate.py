"""Markdown regeneration from parsed hierarchical structures."""

from headhunter.models import HierarchyContext


def to_markdown(
    hierarchy: list[HierarchyContext],
    metadata: dict[str, object] | None = None,
) -> str:
    """Regenerates Markdown from parsed hierarchical structure.

    This function converts a parsed document structure back into clean, properly
    formatted Markdown. It processes the hierarchy linearly, converting headings
    and content blocks according to the following rules:

    - YAML front matter is generated from metadata if provided
    - Standard headings use hash (#) format based on hierarchical level
    - Inline headings use bold (**text:**) format
    - Inline headings are merged with immediate child content on the same line
    - Content blocks are preserved as-is with single blank line spacing
    - Original text case is preserved (including ALL CAPS)

    Args:
        hierarchy: List of HierarchyContext objects representing the document structure.
        metadata: Optional metadata dictionary to include as YAML front matter.

    Returns:
        Regenerated Markdown string with YAML front matter (if metadata provided)
        and properly formatted headings and content.
    """
    lines: list[str] = []

    if metadata:
        lines.append("---")
        for key, value in metadata.items():
            lines.append(f"{key}: {value}")
        lines.append("---")
        lines.append("")

    i = 0
    while i < len(hierarchy):
        ctx = hierarchy[i]
        token = ctx.token

        if token.type == "heading":
            is_inline = token.metadata and token.metadata.is_inline
            has_next = i + 1 < len(hierarchy)
            next_is_content = (
                has_next
                and hierarchy[i + 1].token.type == "content"
                and hierarchy[i + 1].level == ctx.level + 1
            )

            if is_inline and has_next and next_is_content:
                content = hierarchy[i + 1].token.content
                lines.append(f"**{token.content}:** {content}")
                lines.append("")
                i += 2
            elif is_inline:
                lines.append(f"**{token.content}:**")
                lines.append("")
                i += 1
            else:
                hash_count = min(ctx.level, 6)
                hashes = "#" * hash_count
                lines.append(f"{hashes} {token.content}")
                lines.append("")
                i += 1

        else:  # token.type == "content"
            lines.append(token.content)
            lines.append("")
            i += 1

    return "\n".join(lines).rstrip() + "\n"
