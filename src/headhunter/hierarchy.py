"""Hierarchy computation module for building hierarchical structure from tokens."""

from headhunter import config as _config
from headhunter import models

logger = _config.get_logger(__name__)


class HierarchyBuilder:
    """Builds hierarchical structure from parsed tokens.

    This class computes hierarchical levels for tokens based on heading types,
    maintaining state and tracking parent relationships to create a complete
    hierarchy representation.
    """

    def __init__(self) -> None:
        """Initializes the HierarchyBuilder."""
        pass

    def _compute_all_caps_level(
        self,
        metadata: models.HeadingMetadata,
        state: models.HierarchyState,
        heading_stack: list[tuple[int, str, models.HeadingMetadata]],
    ) -> int:
        """Computes level for all-caps headings.

        First all-caps heading sets the level contextually, all subsequent
        all-caps headings use that same fixed level.

        Args:
            metadata: The metadata of the current heading.
            state: The current hierarchy state.
            heading_stack: The current heading stack.

        Returns:
            The computed level for the all-caps heading.
        """
        if state.all_caps_level is None:
            level = 1 if not heading_stack else state.last_heading_level + 1
            state.all_caps_level = level
        else:
            level = state.all_caps_level

        # Reset asterisk state when we encounter an all-caps heading with asterisk
        # markers. This ensures that the next asterisk heading after an all-caps
        # asterisk heading starts fresh without reference to previous asterisk levels
        if metadata.is_asterisk:
            state.last_asterisk_level = None
            state.last_asterisk_marker_count = None

        return level

    def _compute_inline_level(
        self, heading_stack: list[tuple[int, str, models.HeadingMetadata]]
    ) -> int:
        """Computes level for inline headings.

        Inline headings are one level deeper than the last heading on the stack.

        Args:
            heading_stack: The current heading stack.

        Returns:
            The computed level for the inline heading.
        """
        return 1 if not heading_stack else heading_stack[-1][0] + 1

    def _compute_hash_level(
        self,
        marker_count: int,
        state: models.HierarchyState,
        heading_stack: list[tuple[int, str, models.HeadingMetadata]],
    ) -> int:
        """Computes level for hash headings.

        Uses formula: level = last_hash_level + (marker_count - last_hash_marker_count)

        Args:
            marker_count: Number of hash markers in the current heading.
            state: The current hierarchy state.
            heading_stack: The current heading stack.

        Returns:
            The computed level for the hash heading.
        """
        if not heading_stack:
            level = 1
        elif (
            state.last_hash_level is not None
            and state.last_hash_marker_count is not None
        ):
            level = state.last_hash_level + (
                marker_count - state.last_hash_marker_count
            )
        else:
            level = state.last_heading_level + 1

        state.last_hash_level = level
        state.last_hash_marker_count = marker_count
        state.previous_heading_was_hash = True

        return level

    def _compute_asterisk_level(
        self,
        marker_count: int,
        state: models.HierarchyState,
        heading_stack: list[tuple[int, str, models.HeadingMetadata]],
    ) -> int:
        """Computes level for asterisk headings.

        Uses custom ordering for binary comparison: bold (2) < bold+italic (3) <
        italic (1). Level changes by +1 or -1 based on whether current heading is
        deeper or shallower in the hierarchy compared to the previous asterisk heading.

        The mapping establishes a hierarchy where:
        - 2 asterisks (bold) → order 1 (highest level in hierarchy)
        - 3 asterisks (bold+italic) → order 2 (middle level)
        - 1 asterisk (italic) → order 3 (lowest level in hierarchy)

        Args:
            marker_count: Number of asterisk markers in the current heading.
            state: The current hierarchy state.
            heading_stack: The current heading stack.

        Returns:
            The computed level for the asterisk heading.
        """
        # Asterisk count to hierarchical order mapping
        ORDER_MAP: dict[int, int] = {2: 1, 3: 2, 1: 3}

        if not heading_stack:
            level = 1
        elif state.previous_heading_was_hash:
            level = state.last_heading_level + 1
        elif (
            state.last_asterisk_level is not None
            and state.last_asterisk_marker_count is not None
        ):
            current_order = ORDER_MAP[marker_count]
            prev_order = ORDER_MAP[state.last_asterisk_marker_count]

            # Binary comparison: only increment/decrement by 1
            if current_order > prev_order:
                # Current is deeper in hierarchy (e.g., bold -> italic)
                level = state.last_asterisk_level + 1
            elif current_order < prev_order:
                # Current is shallower in hierarchy (e.g., italic -> bold)
                level = state.last_asterisk_level - 1
            else:
                # Same level (e.g., bold -> bold)
                level = state.last_asterisk_level
        else:
            level = state.last_heading_level + 1

        state.last_asterisk_level = level
        state.last_asterisk_marker_count = marker_count
        state.previous_heading_was_hash = False

        return level

    def _compute_heading_level(
        self,
        token: models.Token,
        state: models.HierarchyState,
        heading_stack: list[tuple[int, str, models.HeadingMetadata]],
    ) -> int:
        """Computes the hierarchical level for a heading token.

        Delegates to specific computation methods based on heading type. The
        computation follows a priority order: all-caps (regardless of marker),
        hash headings, then asterisk headings. Inline asterisk headings with
        colon format (e.g., **Label:**) are treated separately.

        Args:
            token: The heading token to compute level for.
            state: The current hierarchy state.
            heading_stack: The current heading stack.

        Returns:
            The computed hierarchical level.
        """
        metadata = token.metadata
        if metadata is None:
            raise ValueError(f"Heading token missing metadata: {token}")

        if metadata.is_all_caps:
            return self._compute_all_caps_level(metadata, state, heading_stack)
        elif metadata.is_hash:
            return self._compute_hash_level(metadata.marker_count, state, heading_stack)
        else:  # metadata.is_asterisk
            if metadata.is_inline:
                return self._compute_inline_level(heading_stack)
            else:
                return self._compute_asterisk_level(
                    metadata.marker_count, state, heading_stack
                )

    def _create_hierarchy_context(
        self,
        token: models.Token,
        level: int,
        heading_stack: list[tuple[int, str, models.HeadingMetadata]],
    ) -> models.HierarchyContext:
        """Creates a HierarchyContext for a token.

        Args:
            token: The token to create context for.
            level: The hierarchical level of the token.
            heading_stack: The current heading stack.

        Returns:
            A HierarchyContext object with parent information extracted from the stack.
        """
        parents = [h[1] for h in heading_stack]
        parent_types = [h[2].signature for h in heading_stack]

        return models.HierarchyContext(
            token=token,
            level=level,
            parents=parents,
            parent_types=parent_types,
        )

    def _update_heading_stack(
        self,
        heading_stack: list[tuple[int, str, models.HeadingMetadata]],
        level: int,
        token: models.Token,
    ) -> None:
        """Updates the heading stack with a new heading.

        Pops headings with level >= current level, then pushes the new heading.

        Args:
            heading_stack: The heading stack to update.
            level: The level of the new heading.
            token: The new heading token.
        """
        while heading_stack and heading_stack[-1][0] >= level:
            heading_stack.pop()
        assert type(token.metadata) is models.HeadingMetadata  # for mypy
        heading_stack.append((level, token.content, token.metadata))

    def _should_pop_inline_heading(
        self, context_list: list[models.HierarchyContext]
    ) -> bool:
        """Checks if previous token was an inline colon heading that should be popped.

        Only inline colon headings (**Label:**) should be popped after their content.
        Regular headings that happen to be extracted inline should remain on the stack.

        Args:
            context_list: The list of hierarchy contexts built so far.

        Returns:
            True if the previous token was an inline colon heading, False otherwise.
        """
        if not context_list or len(context_list) < 2:
            return False

        prev_context = context_list[-2]
        if prev_context.token.type != "heading":
            return False

        metadata = prev_context.token.metadata
        return metadata is not None and metadata.is_inline

    def build(
        self,
        tokens: list[models.Token],
        initial_state: models.HierarchyState | None = None,
        start_index: int = 0,
    ) -> tuple[list[models.HierarchyContext], list[str]]:
        """Builds hierarchical context for all tokens.

        This method traverses tokens once and computes complete hierarchical
        information:
        - Assigns levels to all tokens based on heading hierarchy
        - Tracks parent headings and their metadata
        - Maintains a stack to track the current position in the hierarchy

        The level assignment follows these rules:
        - First heading gets level 1
        - All-caps headings: First encounter sets the level contextually, all subsequent
          all-caps headings use that same fixed level
        - Inline headings: HierarchyState is not updated since it can only have a
          content that is leaf; level = last_heading_level + 1
        - Hash headings: level = last_hash_level + (marker_count -
          last_hash_marker_count)
        - Asterisk headings: Use asterisk ordering (bold < bold+italic < italic)
        - Content tokens: level = last_heading_level + 1 (or 1 if no headings)

        Args:
            tokens: List of tokens to build hierarchy for.
            initial_state: Optional HierarchyState to start with (for partial rebuilds).
            start_index: Index to start processing from (for partial rebuilds).

        Returns:
            A tuple of (hierarchy_contexts, warnings) where hierarchy_contexts is a list
            of HierarchyContext objects and warnings is a list of warning messages.
        """
        warnings: list[str] = []

        if not tokens:
            warning_msg = "No tokens provided for hierarchy building"
            logger.debug(warning_msg)
            warnings.append(warning_msg)
            return [], warnings

        context_list: list[models.HierarchyContext] = []
        heading_stack: list[tuple[int, str, models.HeadingMetadata]] = []
        state = initial_state if initial_state is not None else models.HierarchyState()

        for token in tokens[start_index:]:
            if token.type == "heading":
                level = self._compute_heading_level(token, state, heading_stack)

                context = self._create_hierarchy_context(token, level, heading_stack)
                context_list.append(context)

                self._update_heading_stack(heading_stack, level, token)

                # Update state (but NOT for inline colon headings)
                metadata = token.metadata
                if metadata is not None and not metadata.is_inline:
                    state.last_heading_level = level

            elif token.type == "content":
                # Calculate level: Use the level of the last heading on stack + 1
                # (The stack includes inline headings, while last_heading_level doesn't)
                level = heading_stack[-1][0] + 1 if heading_stack else 1

                context = self._create_hierarchy_context(token, level, heading_stack)
                context_list.append(context)

                # If the previous token was an inline heading, pop it from stack
                # since content after inline headings is always a leaf
                if self._should_pop_inline_heading(context_list):
                    heading_stack.pop()

        if warnings:
            logger.debug(
                f"Hierarchy building completed with {len(warnings)} warning(s)"
            )

        return context_list, warnings
