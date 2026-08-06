from abc import ABC, abstractmethod
from enum import Enum
import logging

from memory.schema import Message, MessageType, RoleEnum

logger = logging.getLogger("Harborstone.Memory")


class MemoryAction(str, Enum):
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
    Default routing policy.

    Rules:
    - SUMMARY -> Semantic Memory
    - SYSTEM -> Keep
    - Large messages -> Episodic Memory
    - Everything else -> Keep
    """

    def decide(self, message: Message) -> MemoryAction:

        if message.msg_type == MessageType.SUMMARY:
            logger.info(
                f"[PROMOTE] seq={message.sequence} -> SEMANTIC | "
                "Reason=Summary message"
            )
            return MemoryAction.SEMANTIC

        if message.role == RoleEnum.SYSTEM:
            logger.info(
                f"[KEEP] seq={message.sequence} | "
                "Reason=System message"
            )
            return MemoryAction.KEEP

        if message.token_count > 150:
            logger.info(
                f"[PROMOTE] seq={message.sequence} -> EPISODIC | "
                f"Reason=Large message ({message.token_count} tokens)"
            )
            return MemoryAction.EPISODIC

        logger.info(
            f"[KEEP] seq={message.sequence} | "
            "Reason=Default policy"
        )

        return MemoryAction.KEEP