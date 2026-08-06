from memory.scratchpad import Scratchpad


def test_basic_operations():

    s = Scratchpad()

    s.set("name", "Mohamed")

    assert s.get("name") == "Mohamed"

    assert s.exists("name")

    s.delete("name")

    assert not s.exists("name")


def test_snapshot():

    s = Scratchpad()

    s.set("task", "Memory")

    snap = s.snapshot()

    assert snap["task"] == "Memory"

    s.clear()

    assert s.size == 0