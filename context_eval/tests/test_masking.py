from context_eval.long_context_cases import generate_long_context_case
from context_eval.observation_masking import ObservationMaskingStrategy
from memory.schema import MessageType


def test_observation_masking_masks_old_tool_outputs():
    """
    Verify that old tool outputs are masked
    while the newest tool outputs remain visible.
    """

    messages, _ = generate_long_context_case()

    strategy = ObservationMaskingStrategy(
        keep_recent_tool_outputs=3
    )

    pruned = strategy.prune(messages)

    tool_messages = [
        msg
        for msg in pruned
        if msg.msg_type == MessageType.TOOL_RESULT
    ]

    # There should be 30 tool outputs
    assert len(tool_messages) == 30

    masked = [
        msg
        for msg in tool_messages
        if msg.is_masked
    ]

    visible = [
        msg
        for msg in tool_messages
        if not msg.is_masked
    ]

    # Old tool outputs should be masked
    assert len(masked) == 27

    # Only the latest 3 remain visible
    assert len(visible) == 3

    # Masked messages should contain placeholder text
    assert all(
        msg.content == "[TOOL OUTPUT MASKED]"
        for msg in masked
    )