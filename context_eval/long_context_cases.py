from typing import List, Tuple

from memory.schema import (
    Message,
    MessageType,
    RoleEnum,
)


def _build_case(
    important_fact: str,
    assistant_reply: str,
    final_question: str,
    expected_phrase: str,
) -> Tuple[List[Message], str]:
    """
    Builds one synthetic long-context conversation.
    """

    messages = []
    sequence = 1

    def add(role, content, msg_type=MessageType.CHAT):
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

    # Important information
    add(RoleEnum.USER, important_fact)
    add(RoleEnum.ASSISTANT, assistant_reply)

    # Large amount of tool output
    for i in range(30):

        add(
            RoleEnum.TOOL,
            f"Database query result #{i+1}",
            MessageType.TOOL_RESULT,
        )

        add(
            RoleEnum.ASSISTANT,
            f"Processed database result #{i+1}",
        )

    # Final question
    add(
        RoleEnum.USER,
        final_question,
    )

    return messages, expected_phrase


def generate_test_case_1():

    return _build_case(

        important_fact=(
            "Claim CLM003 has a fraud score of 82. "
            "Do not approve it without manual review."
        ),

        assistant_reply=(
            "Manual review is required."
        ),

        final_question=(
            "Can this claim be approved immediately?"
        ),

        expected_phrase="manual review",
    )

def generate_test_case_2():

    return _build_case(

        important_fact=(
            "Customer C102 is a VIP policy holder."
        ),

        assistant_reply=(
            "VIP priority has been recorded."
        ),

        final_question=(
            "Should this claim receive priority handling?"
        ),

        expected_phrase="VIP",
    )

def generate_test_case_3():

    return _build_case(

        important_fact=(
            "Policy POL205 has a maximum coverage limit of $15,000."
        ),

        assistant_reply=(
            "Coverage limit recorded."
        ),

        final_question=(
            "Can the customer receive a payout of $20,000?"
        ),

        expected_phrase="$15,000",
    )


def generate_test_case_4():

    return _build_case(

        important_fact=(
            "Policy POL410 expired on January 15, 2025."
        ),

        assistant_reply=(
            "The policy is expired."
        ),

        final_question=(
            "Should this insurance claim be approved?"
        ),

        expected_phrase="expired",
    )


def generate_test_case_5():

    return _build_case(

        important_fact=(
            "The police report is missing from claim CLM410."
        ),

        assistant_reply=(
            "Police report must be submitted first."
        ),

        final_question=(
            "Can payment processing begin?"
        ),

        expected_phrase="police report",
    )


def generate_test_case_6():

    return _build_case(

        important_fact=(
            "Vehicle inspection has not been completed yet."
        ),

        assistant_reply=(
            "Inspection is still pending."
        ),

        final_question=(
            "Can the repair process start now?"
        ),

        expected_phrase="inspection",
    )

def generate_test_case_7():

    return _build_case(

        important_fact=(
            "Customer C501 has a previous fraud investigation on record."
        ),

        assistant_reply=(
            "Previous fraud history noted."
        ),

        final_question=(
            "Can this claim be automatically approved?"
        ),

        expected_phrase="fraud",
    )


def generate_test_case_8():

    return _build_case(

        important_fact=(
            "Fire claim CLM720 requires an investigation before payment."
        ),

        assistant_reply=(
            "Investigation is mandatory."
        ),

        final_question=(
            "Can compensation be paid immediately?"
        ),

        expected_phrase="investigation",
    )


def generate_test_case_9():

    return _build_case(

        important_fact=(
            "Claim ID CLM900 already exists in the database."
        ),

        assistant_reply=(
            "Duplicate claim detected."
        ),

        final_question=(
            "Should a new claim be created?"
        ),

        expected_phrase="duplicate",
    )


def generate_test_case_10():

    return _build_case(

        important_fact=(
            "Claims above $50,000 require supervisor approval."
        ),

        assistant_reply=(
            "Supervisor approval is required."
        ),

        final_question=(
            "Can this high-value claim be approved now?"
        ),

        expected_phrase="supervisor",
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

def generate_all_test_cases():
    """
    Returns all long-context evaluation cases.
    """

    return [

        generate_test_case_1(),

        generate_test_case_2(),

        generate_test_case_3(),

        generate_test_case_4(),

        generate_test_case_5(),

        generate_test_case_6(),

        generate_test_case_7(),

        generate_test_case_8(),

        generate_test_case_9(),

        generate_test_case_10(),
    ]