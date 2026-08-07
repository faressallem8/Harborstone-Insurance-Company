from typing import List, Tuple

from memory.schema import (
    Message,
    MessageType,
    RoleEnum,
)


def generate_long_context_case() -> Tuple[List[Message], str]:
    """
    Creates a long conversation that simulates
    a real insurance claim investigation.
    """

    messages: List[Message] = []

    sequence = 1

    def add_message(
        role: RoleEnum,
        content: str,
        msg_type: MessageType = MessageType.CHAT,
    ) -> None:

        nonlocal sequence

        messages.append(
            Message(
                conversation_id="evaluation_case",
                message_id=f"msg_{sequence}",
                sequence=sequence,
                role=role,
                msg_type=msg_type,
                content=content,
                token_count=max(1, len(content) // 4),
            )
        )

        sequence += 1

    # Important early information.
    add_message(
        RoleEnum.USER,
        "Claim CLM003 has a fraud score of 82. Do not approve it without manual review."
    )

    add_message(
        RoleEnum.ASSISTANT,
        "Understood. I will remember that manual review is required."
    )

    # Simulate many tool calls.
    for i in range(30):

        add_message(
            RoleEnum.TOOL,
            f"Database query result #{i + 1}",
            MessageType.TOOL_RESULT,
        )

        add_message(
            RoleEnum.ASSISTANT,
            f"Processed database result #{i + 1}"
        )

    # Final question.
    add_message(
        RoleEnum.USER,
        "Can this claim be approved immediately?"
    )

    return (
    messages,
    "manual review"
    )