from enum import Enum
from abc import ABC, abstractmethod

from memory.schema import Message, MessageType


class MemoryAction(Enum):
    KEEP = "keep"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    DROP = "drop"


class BasePromotionStrategy(ABC):

    @abstractmethod
    def decide(self, message: Message) -> MemoryAction:
        pass


class DefaultPromotionStrategy(BasePromotionStrategy):
    """
    Decide where a Short-Term Memory message should go.

    Priority:

    1. Explicit personal fact -> Semantic Memory
    2. Summary -> Semantic Memory
    3. Large message -> Episodic Memory
    4. Normal message -> Keep in Short-Term Memory
    """

    LARGE_MESSAGE_THRESHOLD = 700

    def decide(self, message: Message) -> MemoryAction:

        # ====================================================
        # 1. EXPLICIT SEMANTIC FACT
        # ====================================================

        fact_key = (
            message.metadata.get("fact_key")
            if message.metadata
            else None
        )

        if fact_key:
            return MemoryAction.SEMANTIC

        # ====================================================
        # 2. SUMMARY
        # ====================================================

        if message.msg_type == MessageType.SUMMARY:
            return MemoryAction.SEMANTIC

        # ====================================================
        # 3. LARGE MESSAGE
        # ====================================================

        content = message.content or ""

        if isinstance(content, str):

            if len(content) >= self.LARGE_MESSAGE_THRESHOLD:
                return MemoryAction.EPISODIC

        # ====================================================
        # 4. NORMAL CHAT
        # ====================================================

        return MemoryAction.KEEP