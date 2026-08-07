from abc import ABC, abstractmethod
from typing import List

from memory.schema import Message


class BaseContextStrategy(ABC):
    """
    Base interface for all context management strategies.
    Every strategy receives the conversation messages
    and returns the messages that should be sent to the LLM.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def prune(
        self,
        messages: List[Message],
    ) -> List[Message]:
        """
        Apply the context management strategy.

        Args:
            messages: Full conversation history.

        Returns:
            A pruned version of the conversation.
        """
        pass

    def __str__(self) -> str:
        return self.name