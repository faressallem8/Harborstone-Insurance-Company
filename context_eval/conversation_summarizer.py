import os
from typing import List

from groq import Groq

from memory.schema import Message

from dotenv import load_dotenv

load_dotenv()


COMPACT_PROMPT = """
Summarize the conversation below.

Preserve:
- decisions made
- unresolved issues
- key findings

Discard:
- redundant tool output
- superseded reasoning

Write a concise summary.
"""


class ConversationSummarizer:
    """
    Uses the LLM to summarize old conversation history.
    """

    def __init__(self):

        self.client = Groq(
            api_key=os.getenv("GROQ_API_KEY")
        )

        self.model = os.getenv(
            "GROQ_MODEL",
            "llama-3.3-70b-versatile",
        )

    def summarize(
        self,
        messages: List[Message],
    ) -> str:

        # Convert conversation into plain text.
        conversation = "\n".join(
            f"{msg.role.value}: {msg.content}"
            for msg in messages
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": COMPACT_PROMPT,
                },
                {
                    "role": "user",
                    "content": conversation,
                },
            ],
            temperature=0,
        )

        return response.choices[0].message.content.strip()