from enum import Enum
from abc import ABC, abstractmethod

from memory.schema import Message, MessageType


class MemoryAction(Enum):
    EPISODIC = "episodic"
    DROP = "drop"


class BasePromotionStrategy(ABC):

    @abstractmethod
    def decide(self, message: Message) -> MemoryAction:
        pass


class DefaultPromotionStrategy(BasePromotionStrategy):

    LARGE_MESSAGE_THRESHOLD = 700

    def decide(self, message: Message) -> MemoryAction:

        # ====================================================
        # 1. EXPLICIT PERSONAL FACT
        # ====================================================

        fact_key = (
            message.metadata.get("fact_key")
            if message.metadata
            else None
        )

        if fact_key:

            print(
                f"[ROUTER] Message {message.sequence} "
                f"-> EPISODIC | Reason: explicit fact "
                f"(fact_key={fact_key})"
            )

            return MemoryAction.EPISODIC

        # ====================================================
        # 2. SUMMARY
        # ====================================================

        if message.msg_type == MessageType.SUMMARY:

            print(
                f"[ROUTER] Message {message.sequence} "
                f"-> EPISODIC | Reason: summary"
            )

            return MemoryAction.EPISODIC

        # ====================================================
        # 3. LARGE MESSAGE
        # ====================================================

        content = message.content or ""

        if isinstance(content, str):

            if len(content) >= self.LARGE_MESSAGE_THRESHOLD:

                print(
                    f"[ROUTER] Message {message.sequence} "
                    f"-> EPISODIC | Reason: large message "
                    f"(length={len(content)})"
                )

                return MemoryAction.EPISODIC

        # ====================================================
        # 4. NORMAL / TEMPORARY CHAT
        # ====================================================

        print(
            f"[ROUTER] Message {message.sequence} "
            f"-> DROP | Reason: temporary/non-important message"
        )

        return MemoryAction.DROP