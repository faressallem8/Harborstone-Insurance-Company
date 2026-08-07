from context_eval.sliding_window import SlidingWindowStrategy
from context_eval.observation_masking import (
    ObservationMaskingStrategy,
)
from context_eval.recursive_summarization import (
    RecursiveSummarizationStrategy,
)
from context_eval.zone_based_pruning import (
    ZoneBasedPruningStrategy,
)

from context_eval.evaluator import ContextEvaluator
from context_eval.long_context_cases import (
    generate_long_context_case,
)


def main():

    # Build one long conversation
    messages, expected_phrase = generate_long_context_case()

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

    evaluator = ContextEvaluator(
        strategies
    )

    results = evaluator.evaluate(
        messages,
        expected_phrase,
    )

    print("\n===== Context Evaluation =====\n")

    print(
        f"{'Strategy':28}"
        f"{'Original':>10}"
        f"{'Remain':>10}"
        f"{'Removed':>10}"
        f"{'Accuracy':>12}"
        f"{'Latency':>12}"
    )

    print("-" * 82)

    for result in results:

        print(
            f"{result.strategy_name:28}"
            f"{result.original_tokens:>10}"
            f"{result.remaining_tokens:>10}"
            f"{result.tokens_removed:>10}"
            f"{result.accuracy:>12.2f}"
            f"{result.latency:>12.6f}\n"
        )


if __name__ == "__main__":
    main()