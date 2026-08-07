from typing import List

from memory.schema import Message, MessageType, RoleEnum
from context_eval.base_strategy import BaseContextStrategy
from context_eval.conversation_summarizer import ConversationSummarizer


class ZoneBasedPruningStrategy(BaseContextStrategy):
    """
    Divides the conversation into four zones.
    Each zone uses a different pruning strategy.
    """

    def __init__(self):
        super().__init__("Zone-Based Pruning")
        self.summarizer = ConversationSummarizer()

    def prune(
        self,
        messages: List[Message],
    ) -> List[Message]:

        # Short conversations do not need pruning.
        if len(messages) <= 12:
            return list(messages)

        total = len(messages)
        zone_size = total // 4

        zone4 = messages[:zone_size]
        zone3 = messages[zone_size:zone_size * 2]
        zone2 = messages[zone_size * 2:zone_size * 3]
        zone1 = messages[zone_size * 3:]

        pruned: List[Message] = []

        # Zone 4:
        # Delete completely.
        # (Nothing is added.)

        # Zone 3:
        # Replace with one summary.
        if zone3:

            summary = self.summarizer.summarize(zone3)

            pruned.append(
                Message(
                    conversation_id=zone3[0].conversation_id,
                    message_id="zone3_summary",
                    sequence=0,
                    role=RoleEnum.SYSTEM,
                    msg_type=MessageType.SUMMARY,
                    content=f"Earlier context:\n{summary}",
                    token_count=max(1, len(summary) // 4),
                )
            )

        # Zone 2:
        # Mask tool outputs.
        for msg in zone2:

            if msg.msg_type == MessageType.TOOL_RESULT:

                pruned.append(
                    msg.model_copy(
                        update={
                            "content": "[TOOL OUTPUT MASKED]",
                            "is_masked": True,
                            "token_count": 1,
                        }
                    )
                )

            else:
                pruned.append(msg)

        # Zone 1:
        # Keep everything.
        pruned.extend(zone1)

        return pruned