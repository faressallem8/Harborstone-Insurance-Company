from typing import List
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
    Periodically consolidates Short-Term Memory into
    Episodic / Semantic Memory.
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

    def consolidate(self):

        logger.info("===== Consolidation Started =====")

        remaining_messages: List[Message] = []

        for message in self.short_term.get_messages():

            decision = self.strategy.decide(message)

            if decision == MemoryAction.KEEP:

                remaining_messages.append(message)

                logger.info(
                    f"Message {message.sequence} kept in Short-Term Memory."
                )

            elif decision == MemoryAction.EPISODIC:

                self.episodic.add(message)

                logger.info(
                    f"Message {message.sequence} promoted to Episodic Memory."
                )

            elif decision == MemoryAction.SEMANTIC:

                self._update_semantic_memory(message)

            elif decision == MemoryAction.DROP:

                logger.info(
                    f"Message {message.sequence} dropped."
                )

        self.short_term.replace_messages(remaining_messages)

        self.semantic.expire()

        logger.info("===== Consolidation Finished =====")

    def _update_semantic_memory(
        self,
        message: Message,
    ):

        fact_key = message.metadata.get("fact_key")

        if not fact_key:

            logger.warning(
                f"Message {message.sequence} skipped because no fact_key exists."
            )

            return

        existing = self.semantic.get(fact_key)

        if existing is not None:

            logger.info(
                f"Conflict detected for fact '{fact_key}'. "
                "Previous version will be archived."
            )

        self.semantic.add(message)

        logger.info(
            f"Semantic fact '{fact_key}' stored successfully."
        )