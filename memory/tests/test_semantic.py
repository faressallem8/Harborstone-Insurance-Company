from datetime import datetime, timedelta, timezone

from memory.semantic_memory import SemanticMemory
from memory.schema import (
    Message,
    RoleEnum,
)


def test_add():

    memory = SemanticMemory()

    msg = Message(
    conversation_id="1",
    message_id="1",
    sequence=1,
    role=RoleEnum.USER,
    content="Fact",
    metadata={
        "fact_key": "customer_name"
    }
)

 
    msg = Message(
    conversation_id="1",
    message_id="1",
    sequence=1,
    role=RoleEnum.USER,
    content="Fact",
    metadata={
        "fact_key": "customer_name"
    },
    expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
)
    memory.add(msg)

    memory.expire()

    assert len(memory) == 0

    