from memory.short_term import ShortTermMemory
from memory.episodic_memory import EpisodicMemory
from memory.semantic_memory import SemanticMemory
from memory.consolidation import ConsolidationEngine
from memory.schema import (
    RoleEnum,
    MessageType,
)


def test_consolidation():

    stm = ShortTermMemory()

    episodic = EpisodicMemory()

    semantic = SemanticMemory()

    stm.add_message(
        RoleEnum.USER,
        "A" * 800,
    )

    stm.add_message(
    RoleEnum.ASSISTANT,
    "Summary",
    msg_type=MessageType.SUMMARY,
    metadata={
        "fact_key": "summary"
    },
)

    engine = ConsolidationEngine(
        stm,
        episodic,
        semantic,
    )

    engine.consolidate()

    assert len(episodic) == 1

    assert len(semantic) == 1