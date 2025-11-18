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
        state: models.HierarchyState,
        heading_stack: list[tuple[int, str, dict[str, str | int]]],
    ) -> int:
        """Computes level for all-caps headings.

        First all-caps heading sets the level contextually, all subsequent
        all-caps headings use that same fixed level.

        Args:
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

        # Reset asterisk state when we encounter an all-caps heading
        # This ensures that the next asterisk heading after an all-caps heading
        # starts fresh without reference to previous asterisk levels
        state.last_asterisk_level = None
        state.last_asterisk_marker_count = None

        return level

    def _compute_inline_level(
        self, heading_stack: list[tuple[int, str, dict[str, str | int]]]
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
        heading_stack: list[tuple[int, str, dict[str, str | int]]],
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

        # Update state
        state.last_hash_level = level
        state.last_hash_marker_count = marker_count
        state.previous_heading_was_hash = True

        return level

    def _compute_asterisk_level(
        self,
        marker_count: int,
        state: models.HierarchyState,
        heading_stack: list[tuple[int, str, dict[str, str | int]]],
    ) -> int:
        """Computes level for asterisk headings.

        Uses custom ordering for binary comparison: bold (2) < bold+italic (3) <
        italic (1). Level changes by +1 or -1 based on whether current heading
        is deeper or shallower
        in the hierarchy compared to the previous asterisk heading.

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

        # Update state
        state.last_asterisk_level = level
        state.last_asterisk_marker_count = marker_count
        state.previous_heading_was_hash = False

        return level

    def _compute_heading_level(
        self,
        token: models.Token,
        state: models.HierarchyState,
        heading_stack: list[tuple[int, str, dict[str, str | int]]],
    ) -> int:
        """Computes the hierarchical level for a heading token.

        Delegates to specific computation methods based on heading type.

        Args:
            token: The heading token to compute level for.
            state: The current hierarchy state.
            heading_stack: The current heading stack.

        Returns:
            The computed hierarchical level.
        """
        marker = token.metadata["marker"]
        marker_count = token.metadata["marker_count"]
        case = token.metadata["case"]
        position = token.metadata["position"]

        if case == "all_caps" and position == "standalone":
            return self._compute_all_caps_level(state, heading_stack)
        elif position == "inline":
            return self._compute_inline_level(heading_stack)
        elif marker == "#":
            return self._compute_hash_level(int(marker_count), state, heading_stack)
        elif marker == "*":
            return self._compute_asterisk_level(int(marker_count), state, heading_stack)
        else:
            return state.last_heading_level + 1 if state.last_heading_level > 0 else 1

    def _create_hierarchy_context(
        self,
        token: models.Token,
        level: int,
        heading_stack: list[tuple[int, str, dict[str, str | int]]],
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
        parent_types = [str(h[2]["heading_type"]) for h in heading_stack]

        return models.HierarchyContext(
            token=token,
            level=level,
            parents=parents,
            parent_types=parent_types,
        )

    def _update_heading_stack(
        self,
        heading_stack: list[tuple[int, str, dict[str, str | int]]],
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
        heading_stack.append((level, token.content, token.metadata))

    def _should_pop_inline_heading(
        self, context_list: list[models.HierarchyContext]
    ) -> bool:
        """Checks if the previous token was an inline heading that should be popped.

        Args:
            context_list: The list of hierarchy contexts built so far.

        Returns:
            True if the previous token was an inline heading, False otherwise.
        """
        if not context_list or len(context_list) < 2:
            return False

        prev_context = context_list[-2]
        return (
            prev_context.token.type == "heading"
            and prev_context.token.metadata["position"] == "inline"
        )

    def build(
        self, tokens: list[models.Token]
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
        - Inline headings: Treated as one level above their content (content is always
          leaf)
        - For other headings:
          - Hash headings: level = last_hash_level + (marker_count -
            last_hash_marker_count)
          - Asterisk headings: Use asterisk ordering (bold < bold+italic < italic)
        - Content tokens: level = last_heading_level + 1 (or 1 if no headings)

        Args:
            tokens: List of tokens to build hierarchy for.

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
        heading_stack: list[tuple[int, str, dict[str, str | int]]] = []
        state = models.HierarchyState()

        for token in tokens:
            if token.type == "heading":
                # Compute level for this heading
                level = self._compute_heading_level(token, state, heading_stack)

                # Create context
                context = self._create_hierarchy_context(token, level, heading_stack)
                context_list.append(context)

                # Update heading stack
                self._update_heading_stack(heading_stack, level, token)

                # Update state (but NOT for inline headings - no hierarchy effect)
                if token.metadata["position"] != "inline":
                    state.last_heading_level = level

            elif token.type == "content":
                # Calculate level: Use the level of the last heading on stack + 1
                # (The stack includes inline headings, while last_heading_level doesn't)
                level = heading_stack[-1][0] + 1 if heading_stack else 1

                # Create context
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
