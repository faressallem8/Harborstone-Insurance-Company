from typing import List

from memory.schema import Message
from context_eval.base_strategy import BaseContextStrategy


class SlidingWindowStrategy(BaseContextStrategy):
    """
    Keeps only the most recent messages
    within a fixed-size sliding window.
    """

    def __init__(self, window_size: int = 10):
        super().__init__("Sliding Window")
        self.window_size = window_size

    def prune(
        self,
        messages: List[Message],
    ) -> List[Message]:

        if len(messages) <= self.window_size:
            return list(messages)

        return list(messages[-self.window_size:])