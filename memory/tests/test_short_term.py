from memory.short_term import ShortTermMemory
from memory.schema import RoleEnum


def test_add_message():

    stm = ShortTermMemory()

    stm.add_message(
        role=RoleEnum.USER,
        content="Hello"
    )

    assert stm.message_count == 1
    assert stm.current_token_usage > 0


def test_snapshot_and_rollback():

    stm = ShortTermMemory()

    stm.add_message(
        RoleEnum.USER,
        "First"
    )

    stm.create_snapshot()

    stm.add_message(
        RoleEnum.USER,
        "Second"
    )

    assert stm.message_count == 2

    stm.rollback()

    assert stm.message_count == 1


def test_scratchpad():

    stm = ShortTermMemory()

    stm.update_scratchpad(
        "name",
        "Mohamed"
    )

    assert stm.get_scratchpad()["name"] == "Mohamed"

    stm.remove_scratchpad_key("name")

    assert "name" not in stm.get_scratchpad()