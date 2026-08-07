from typing import List

from memory.schema import Message, MessageType
from context_eval.base_strategy import BaseContextStrategy


class ObservationMaskingStrategy(BaseContextStrategy):
    """
    Masks old tool outputs while preserving
    user and assistant conversation.
    """

    def __init__(self, keep_recent_tool_outputs: int = 3):
        super().__init__("Observation Masking")
        self.keep_recent_tool_outputs = keep_recent_tool_outputs

    def prune(
        self,
        messages: List[Message],
    ) -> List[Message]:

        tool_messages = [
            msg
            for msg in messages
            if msg.msg_type == MessageType.TOOL_RESULT
        ]

        keep_tool_ids = {
            msg.message_id
            for msg in tool_messages[-self.keep_recent_tool_outputs:]
        }

        pruned_messages: List[Message] = []

        for msg in messages:

            if msg.msg_type != MessageType.TOOL_RESULT:
                pruned_messages.append(msg)
                continue

            if msg.message_id in keep_tool_ids:
                pruned_messages.append(msg)
                continue

            masked_msg = msg.model_copy(
                update={
                    "content": "[TOOL OUTPUT MASKED]",
                    "is_masked": True,
                    "token_count": 1,
                }
            )

            pruned_messages.append(masked_msg)

        return pruned_messages