from context_eval.sliding_window import SlidingWindowStrategy
from context_eval.observation_masking import ObservationMaskingStrategy
from context_eval.recursive_summarization import (
    RecursiveSummarizationStrategy,
)
from context_eval.zone_based_pruning import (
    ZoneBasedPruningStrategy,
)

from context_eval.long_context_cases import (
    generate_all_test_cases,
)

from context_eval.evaluator import ContextEvaluator


def main():

    # All context management strategies
    strategies = [

        SlidingWindowStrategy(window_size=10),

        ObservationMaskingStrategy(
            keep_recent_tool_outputs=3
        ),

        RecursiveSummarizationStrategy(
            keep_recent_messages=6
        ),

        ZoneBasedPruningStrategy(),

    ]

    # Generate all evaluation conversations
    test_cases = generate_all_test_cases()

    evaluator = ContextEvaluator(strategies)

    results = evaluator.evaluate(test_cases)

    print("\n\t\t===== Context Evaluation =====\n")

    print(
        f"{'Strategy':30}"
        f"{'Accuracy':>12}"
        f"{'Tokens':>12}"
        f"{'Latency':>14}"
    )
    print("="*70)

    for result in results:

        print(
            f"{result.strategy_name:30}"
            f"{result.accuracy:>11.2%}"
            f"{result.remaining_tokens:>12}"
            f"{result.latency:>14.6f}\n"
        )


if __name__ == "__main__":
    main()