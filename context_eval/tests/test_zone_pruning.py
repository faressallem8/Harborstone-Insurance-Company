from context_eval.long_context_cases import generate_long_context_case
from context_eval.zone_based_pruning import ZoneBasedPruningStrategy


def test_zone_based_pruning():
    """
    Verify that Zone-Based Pruning
    reduces the context size while
    keeping the conversation valid.
    """

    messages, _ = generate_long_context_case()

    strategy = ZoneBasedPruningStrategy()

    pruned = strategy.prune(messages)

    # Context should become smaller
    assert len(pruned) < len(messages)

    # It should still contain messages
    assert len(pruned) > 0

    # The newest user message should still exist
    assert "approved immediately" in str(pruned[-1].content).lower()