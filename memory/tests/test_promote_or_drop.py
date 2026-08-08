from memory.promote_or_drop import (
    DefaultPromotionStrategy,
    MemoryAction,
)

from memory.schema import (
    Message,
    RoleEnum,
    MessageType,
)


def test_summary_goes_semantic():

    strategy = DefaultPromotionStrategy()

    msg = Message(
        conversation_id="1",
        message_id="1",
        sequence=1,
        role=RoleEnum.ASSISTANT,
        msg_type=MessageType.SUMMARY,
        content="summary",
        token_count=10,
    )

    assert strategy.decide(msg) == MemoryAction.SEMANTIC


def test_large_message_goes_episodic():

    strategy = DefaultPromotionStrategy()

    msg = Message(
        conversation_id="1",
        message_id="2",
        sequence=2,
        role=RoleEnum.USER,
        msg_type=MessageType.CHAT,
        content="hello",
        token_count=200,
    )

    assert strategy.decide(msg) == MemoryAction.EPISODIC