from typing import List, Set
import logging

from memory.short_term import ShortTermMemory
from memory.episodic_memory import EpisodicMemory
from memory.semantic_memory import SemanticMemory
from memory.promote_or_drop import (
    BasePromotionStrategy,
    DefaultPromotionStrategy,
    MemoryAction,
)
from memory.schema import Message

logger = logging.getLogger("Harborstone.Memory")


class ConsolidationEngine:
    """
    Memory consolidation pipeline.

    Architecture:

        Short-Term Memory
                |
                v
        Promote-or-Drop Router
             /        \
            /          \
       Episodic        Drop
          |
          v
    Periodic Consolidation
          |
          v
      Semantic Memory

    IMPORTANT:

    The promotion router NEVER writes directly to Semantic Memory.

    Semantic Memory is created or updated ONLY during the
    periodic consolidation phase over Episodic Memory.

    The consolidation layer handles:
        - new semantic facts
        - fact updates
        - conflict resolution
        - version preservation
        - expiration
        - visible decision logging
    """

    def __init__(
        self,
        short_term: ShortTermMemory,
        episodic: EpisodicMemory,
        semantic: SemanticMemory,
        strategy: BasePromotionStrategy | None = None,
    ):
        self.short_term = short_term
        self.episodic = episodic
        self.semantic = semantic
        self.strategy = strategy or DefaultPromotionStrategy()

        # Track episodes that have already been examined during
        # semantic consolidation.
        #
        # This prevents the same episode from being processed
        # repeatedly every time consolidate() runs.
        self._processed_episode_ids: Set[str] = set()

    # ============================================================
    # PUBLIC CONSOLIDATION ENTRY POINT
    # ============================================================

    def consolidate(self):
        """
        Run the complete memory consolidation pipeline.

        Phase 1:
            Short-Term Memory -> Episodic Memory OR Drop

        Phase 2:
            Episodic Memory -> Semantic Memory

        Phase 3:
            Expire stale semantic facts
        """

        logger.info(
            "===================================================="
        )
        logger.info(
            "===== MEMORY CONSOLIDATION STARTED ====="
        )
        logger.info(
            "===================================================="
        )

        # --------------------------------------------------------
        # PHASE 1
        # Short-Term -> Episodic / Drop
        # --------------------------------------------------------

        self._route_short_term_memory()

        # --------------------------------------------------------
        # PHASE 2
        # Episodic -> Semantic
        # --------------------------------------------------------

        self._consolidate_episodic_to_semantic()

        # --------------------------------------------------------
        # PHASE 3
        # Semantic expiration
        # --------------------------------------------------------

        self._expire_semantic_memory()

        logger.info(
            "===================================================="
        )
        logger.info(
            "===== MEMORY CONSOLIDATION FINISHED ====="
        )
        logger.info(
            "===================================================="
        )

    # ============================================================
    # PHASE 1
    # ============================================================

    def _route_short_term_memory(self):
        """
        Ask the promote-or-drop router what should happen
        to every aging Short-Term Memory message.

        The router is intentionally restricted to:

            EPISODIC
            DROP

        It cannot write to Semantic Memory.
        """

        remaining_messages: List[Message] = []

        messages = self.short_term.get_messages()

        logger.info(
            f"[ROUTER] Evaluating {len(messages)} "
            f"Short-Term Memory messages."
        )

        for message in messages:

            decision = self.strategy.decide(message)

            # ----------------------------------------------------
            # PROMOTE -> EPISODIC
            # ----------------------------------------------------

            if decision == MemoryAction.EPISODIC:

                self.episodic.add(message)

                reason = self._promotion_reason(message)

                logger.info(
                    f"[PROMOTE] "
                    f"message_id={message.message_id} | "
                    f"sequence={message.sequence} | "
                    f"action=EPISODIC | "
                    f"reason={reason}"
                )

            # ----------------------------------------------------
            # FORGET -> DROP
            # ----------------------------------------------------

            elif decision == MemoryAction.DROP:

                reason = self._drop_reason(message)

                logger.info(
                    f"[FORGET] "
                    f"message_id={message.message_id} | "
                    f"sequence={message.sequence} | "
                    f"action=DROP | "
                    f"reason={reason}"
                )

            # ----------------------------------------------------
            # KEEP
            # ----------------------------------------------------

            elif decision == MemoryAction.KEEP:

                remaining_messages.append(message)

                logger.info(
                    f"[KEEP] "
                    f"message_id={message.message_id} | "
                    f"sequence={message.sequence} | "
                    f"action=KEEP"
                )

            # ----------------------------------------------------
            # INVALID ROUTER RESULT
            # ----------------------------------------------------

            else:

                logger.error(
                    f"[ROUTER ERROR] Unsupported memory action: "
                    f"{decision}"
                )

                # Safety behavior:
                # Do not silently lose the message.
                remaining_messages.append(message)

        self.short_term.replace_messages(
            remaining_messages
        )

        logger.info(
            f"[ROUTER] Finished. "
            f"Remaining STM messages: "
            f"{len(remaining_messages)}"
        )

    # ============================================================
    # ROUTER REASONING
    # ============================================================

    @staticmethod
    def _promotion_reason(message: Message) -> str:
        """
        Explain why an item was promoted to Episodic Memory.
        """

        metadata = message.metadata or {}

        fact_key = metadata.get("fact_key")

        if fact_key:
            return (
                f"explicit semantic candidate detected "
                f"(fact_key={fact_key}); preserved in Episodic "
                f"Memory before semantic consolidation"
            )

        if message.msg_type.value == "summary":
            return (
                "summary message; preserved because it represents "
                "compressed conversational state"
            )

        content = message.content or ""

        if isinstance(content, str):
            if len(content) >= DefaultPromotionStrategy.LARGE_MESSAGE_THRESHOLD:
                return (
                    f"large message "
                    f"(length={len(content)} >= "
                    f"threshold={DefaultPromotionStrategy.LARGE_MESSAGE_THRESHOLD})"
                )

        return (
            "message selected by the promotion strategy "
            "for episodic preservation"
        )

    @staticmethod
    def _drop_reason(message: Message) -> str:
        """
        Explain why an item was forgotten.
        """

        metadata = message.metadata or {}

        fact_key = metadata.get("fact_key")

        if fact_key:
            return (
                "unexpected DROP for message containing fact_key; "
                "check promotion strategy"
            )

        if message.msg_type.value == "summary":
            return (
                "unexpected DROP for summary; "
                "check promotion strategy"
            )

        content = message.content or ""

        if isinstance(content, str):
            return (
                f"temporary/non-significant message; "
                f"content_length={len(content)} below preservation "
                f"threshold={DefaultPromotionStrategy.LARGE_MESSAGE_THRESHOLD}"
            )

        return (
            "message did not satisfy any preservation rule"
        )

    # ============================================================
    # PHASE 2
    # ============================================================

    def _consolidate_episodic_to_semantic(self):
        """
        Build and update Semantic Memory from Episodic Memory.

        This is the ONLY method in the memory pipeline that
        promotes information into Semantic Memory.

        Handles:

            - new facts
            - unchanged facts
            - conflicting facts
            - updates
            - version preservation

        Non-semantic episodes are ignored.
        """

        logger.info(
            "===== EPISODIC -> SEMANTIC CONSOLIDATION STARTED ====="
        )

        episodes = self.episodic.get_all()

        new_episode_count = 0

        for message in episodes:

            # ----------------------------------------------------
            # Avoid re-processing the same episode
            # ----------------------------------------------------

            if message.message_id in self._processed_episode_ids:
                continue

            new_episode_count += 1

            metadata = message.metadata or {}

            fact_key = metadata.get("fact_key")

            # ----------------------------------------------------
            # Not every episode represents a semantic fact
            # ----------------------------------------------------

            if not fact_key:

                logger.info(
                    f"[EPISODIC] message_id={message.message_id} "
                    f"has no fact_key; retained as episodic-only memory."
                )

                self._processed_episode_ids.add(
                    message.message_id
                )

                continue

            # ----------------------------------------------------
            # Check existing semantic fact
            # ----------------------------------------------------

            existing = self.semantic.get(fact_key)

            # ----------------------------------------------------
            # NEW FACT
            # ----------------------------------------------------

            if existing is None:

                self.semantic.add(message)

                logger.info(
                    f"[NEW FACT] "
                    f"fact_key={fact_key} | "
                    f"value={message.content}"
                )

                self._processed_episode_ids.add(
                    message.message_id
                )

                continue

            # ----------------------------------------------------
            # SAME FACT
            # ----------------------------------------------------

            if self._same_fact(existing, message):

                logger.info(
                    f"[UNCHANGED] "
                    f"fact_key={fact_key} | "
                    f"value already represented in Semantic Memory"
                )

                self._processed_episode_ids.add(
                    message.message_id
                )

                continue

            # ----------------------------------------------------
            # CONFLICT
            # ----------------------------------------------------

            logger.info(
                "----------------------------------------------------"
            )

            logger.info(
                f"[CONFLICT DETECTED] fact_key={fact_key}"
            )

            logger.info(
                f"[CONFLICT] "
                f"previous_value={existing.content}"
            )

            logger.info(
                f"[CONFLICT] "
                f"new_value={message.content}"
            )

            # ----------------------------------------------------
            # Versioning
            # ----------------------------------------------------

            logger.info(
                f"[VERSION] "
                f"archiving previous semantic version for "
                f"fact_key={fact_key}"
            )

            # SemanticMemory.add() is responsible for preserving
            # the previous value in its version history.
            self.semantic.add(message)

            logger.info(
                f"[RESOLVED] "
                f"fact_key={fact_key} | "
                f"active_value={message.content} | "
                f"resolution=latest_episode_wins"
            )

            logger.info(
                "----------------------------------------------------"
            )

            self._processed_episode_ids.add(
                message.message_id
            )

        logger.info(
            f"[CONSOLIDATION] "
            f"New episodes examined={new_episode_count}"
        )

        logger.info(
            "===== EPISODIC -> SEMANTIC CONSOLIDATION FINISHED ====="
        )

    # ============================================================
    # PHASE 3
    # ============================================================

    def _expire_semantic_memory(self):
        """
        Remove semantic facts whose expires_at timestamp
        has passed.
        """

        before = len(self.semantic)

        self.semantic.expire()

        after = len(self.semantic)

        expired_count = before - after

        logger.info(
            f"[EXPIRATION] "
            f"expired_facts={expired_count}"
        )

    # ============================================================
    # FACT COMPARISON
    # ============================================================

    @staticmethod
    def _same_fact(
        old_message: Message,
        new_message: Message,
    ) -> bool:
        """
        Determine whether two semantic candidates contain
        the same fact value.
        """

        old_content = (
            str(old_message.content or "")
            .strip()
            .lower()
        )

        new_content = (
            str(new_message.content or "")
            .strip()
            .lower()
        )

        return old_content == new_content

    # ============================================================
    # OPTIONAL DEBUG HELPERS
    # ============================================================

    def reset_processed_tracking(self):
        """
        Reset the internal consolidation tracking.

        Useful for tests or a fresh consolidation cycle.
        """

        self._processed_episode_ids.clear()

        logger.info(
            "[CONSOLIDATION] Processed episode tracking reset."
        )

    def get_processed_episode_ids(self) -> Set[str]:
        """
        Return IDs of episodes already examined by
        the semantic consolidation layer.
        """

        return set(
            self._processed_episode_ids
        )