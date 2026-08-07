from typing import List

from memory.schema import Message, MessageType, RoleEnum
from context_eval.base_strategy import BaseContextStrategy
from context_eval.conversation_summarizer import ConversationSummarizer


class RecursiveSummarizationStrategy(BaseContextStrategy):
    """
    Replaces old conversation with a single LLM-generated summary
    while keeping the most recent messages.
    """

    def __init__(
        self,
        keep_recent_messages: int = 6,
    ):
        super().__init__("Recursive Summarization")

        self.keep_recent_messages = keep_recent_messages
        self.summarizer = ConversationSummarizer()

    def prune(
        self,
        messages: List[Message],
    ) -> List[Message]:

        # No need to summarize short conversations.
        if len(messages) <= self.keep_recent_messages:
            return list(messages)

        old_messages = messages[:-self.keep_recent_messages]
        recent_messages = messages[-self.keep_recent_messages:]

        # Generate summary using the LLM.
        summary = self.summarizer.summarize(old_messages)

        # Create a summary message.
        summary_message = Message(
            conversation_id=messages[0].conversation_id,
            message_id="summary",
            sequence=0,
            role=RoleEnum.SYSTEM,
            msg_type=MessageType.SUMMARY,
            content=f"Earlier context:\n{summary}",
            token_count=max(1, len(summary) // 4),
        )

        return [summary_message] + recent_messages