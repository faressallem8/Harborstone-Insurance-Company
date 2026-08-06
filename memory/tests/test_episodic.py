from memory.episodic_memory import EpisodicMemory
from memory.schema import (
    Message,
    RoleEnum,
)


def test_add_and_remove():

    memory = EpisodicMemory()

    msg = Message(
        conversation_id="1",
        message_id="1",
        sequence=1,
        role=RoleEnum.USER,
        content="hello",
    )

    memory.add(msg)

    assert len(memory) == 1

    assert memory.remove("1")

    assert len(memory) == 0