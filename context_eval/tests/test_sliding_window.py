import pytest

from context_eval.sliding_window import SlidingWindowStrategy
from context_eval.long_context_cases import generate_long_context_case


def test_sliding_window_keeps_last_messages():
    """
    Verify that only the last N messages remain.
    """

    messages, _ = generate_long_context_case()
    
    strategy = SlidingWindowStrategy(window_size=10)

    pruned = strategy.prune(messages)

    # Should keep only the last 10 messages
    assert len(pruned) == 10

    # Last message must remain
    assert pruned[-1].content == messages[-1].content

    # First kept message should match the original conversation
    assert pruned[0].sequence == messages[-10].sequence