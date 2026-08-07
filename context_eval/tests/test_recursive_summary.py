from context_eval.long_context_cases import generate_long_context_case
from context_eval.recursive_summarization import (
    RecursiveSummarizationStrategy,
)


def test_recursive_summary_reduces_tokens():
    """
    Verify that recursive summarization
    reduces the total token count while
    preserving important information.
    """

    messages, expected_phrase = generate_long_context_case()

    strategy = RecursiveSummarizationStrategy(
        keep_recent_messages=6
    )

    summarized = strategy.prune(messages)

    original_tokens = sum(
        msg.token_count
        for msg in messages
    )

    summarized_tokens = sum(
        msg.token_count
        for msg in summarized
    )

    # Context should become smaller
    assert summarized_tokens < original_tokens

    # Important information should survive
    conversation = " ".join(
        str(msg.content)
        for msg in summarized
    ).lower()

    assert expected_phrase in conversation