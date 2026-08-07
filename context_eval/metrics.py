import time
from dataclasses import dataclass
from typing import List

from memory.schema import Message


@dataclass
class EvaluationMetrics:
    """
    Stores evaluation results for one strategy.
    """

    strategy_name: str

    original_tokens: int
    remaining_tokens: int
    tokens_removed: int

    message_count: int

    latency: float
    accuracy: float


def calculate_token_count(
    messages: List[Message],
) -> int:
    """
    Calculates the total number of tokens.
    """

    return sum(msg.token_count for msg in messages)


def calculate_accuracy(
    messages: List[Message],
    expected_phrase: str,
) -> float:
    """
    Checks whether the important information
    survived after pruning.
    """

    conversation = " ".join(
        str(msg.content)
        for msg in messages
    ).lower()

    if expected_phrase.lower() in conversation:
        return 1.0

    return 0.0


def measure_latency(
    func,
):
    """
    Measures execution time of a strategy.
    """

    start = time.perf_counter()

    result = func()

    latency = time.perf_counter() - start

    return result, latency