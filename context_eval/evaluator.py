from typing import List

from memory.schema import Message

from context_eval.base_strategy import BaseContextStrategy
from context_eval.metrics import (
    EvaluationMetrics,
    calculate_accuracy,
    calculate_token_count,
    measure_latency,
)


class ContextEvaluator:
    """
    Runs all context management strategies
    and collects their evaluation metrics.
    """

    def __init__(
        self,
        strategies: List[BaseContextStrategy],
    ):
        self.strategies = strategies

    def evaluate(
        self,
        messages: List[Message],
        expected_phrase: str,
    ) -> List[EvaluationMetrics]:

        results: List[EvaluationMetrics] = []

        # Tokens before pruning
        original_tokens = calculate_token_count(messages)

        for strategy in self.strategies:

            # Run the strategy and measure latency
            pruned_messages, latency = measure_latency(
                lambda: strategy.prune(messages)
            )

            # Tokens after pruning
            remaining_tokens = calculate_token_count(
                pruned_messages
            )

            tokens_removed = (
                original_tokens - remaining_tokens
            )

            # Check if important information survived
            accuracy = calculate_accuracy(
                pruned_messages,
                expected_phrase,
            )

            results.append(
                EvaluationMetrics(
                    strategy_name=str(strategy),
                    original_tokens=original_tokens,
                    remaining_tokens=remaining_tokens,
                    tokens_removed=tokens_removed,
                    message_count=len(pruned_messages),
                    latency=latency,
                    accuracy=accuracy,
                )
            )

        return results