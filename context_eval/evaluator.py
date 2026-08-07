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
        test_cases,
    ):

        results = []

        for strategy in self.strategies:

            total_accuracy = 0.0
            total_latency = 0.0
            total_tokens = 0
            total_original_tokens = 0
            

            for messages, expected_phrase in test_cases:

                original_tokens = calculate_token_count(messages)
                total_original_tokens += original_tokens

                pruned_messages, latency = measure_latency(
                    lambda: strategy.prune(messages)
                )

                remaining_tokens = calculate_token_count(
                    pruned_messages
                )

                accuracy = calculate_accuracy(
                    pruned_messages,
                    expected_phrase,
                )

                total_accuracy += accuracy
                total_latency += latency
                total_tokens += remaining_tokens

            case_count = len(test_cases)

            average_original_tokens = (
                total_original_tokens // case_count
            )
            
            average_remaining_tokens = (
                total_tokens // case_count
            )
            
            average_tokens_removed = (
                average_original_tokens
                - average_remaining_tokens
            )

            results.append(

                EvaluationMetrics(
                                
                    strategy_name=str(strategy),
                
                    original_tokens=average_original_tokens,
                
                    remaining_tokens=average_remaining_tokens,
                
                    tokens_removed=average_tokens_removed,
                
                    message_count=case_count,
                
                    latency=total_latency / case_count,
                
                    accuracy=total_accuracy / case_count,
                
                )
            )

        return results