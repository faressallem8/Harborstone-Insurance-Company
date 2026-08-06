import uuid
import threading
import logging
from collections.abc import Sequence
from typing import Any, Optional

from memory.schema import (
    Message,
    MessageType,
    RoleEnum,
    ShortTermMemorySnapshot,
)
from memory.token_counter import BaseTokenCounter, SimpleTokenCounter
from memory.types import Metadata
from memory.exceptions import (
    MemoryOverflowError,
    MemoryValidationError,
    MemoryRollbackError,
)
from config import settings

logger = logging.getLogger("Harborstone.Memory")


class ShortTermMemory:
    def __init__(
        self,
        conversation_id: str = "default_conv",
        max_token_limit: Optional[int] = None,
        token_counter: Optional[BaseTokenCounter] = None,
    ):
        self.conversation_id = conversation_id
        self.max_token_limit = (
            max_token_limit or settings.default_max_token_limit
        )
        self.token_counter = token_counter or SimpleTokenCounter()

        self._messages: list[Message] = []
        self._scratchpad: Metadata = {}
        self._current_token_usage: int = 0
        self._sequence_counter: int = 0

        self._lock = threading.RLock()
        self._snapshot: Optional[ShortTermMemorySnapshot] = None

    def get_read_snapshot_messages(self) -> tuple[Message, ...]:
        with self._lock:
            return tuple(self._messages)

    def get_messages(self) -> tuple[Message, ...]:
        with self._lock:
            return tuple(self._messages)

    @property
    def current_token_usage(self) -> int:
        return self._current_token_usage

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def create_snapshot(self) -> None:
        with self._lock:
            self._snapshot = ShortTermMemorySnapshot(
                sequence_counter=self._sequence_counter,
                current_token_usage=self._current_token_usage,
                scratchpad_state=dict(self._scratchpad),
                messages_references=list(self._messages),
            )

            logger.info(
                f"Snapshot created "
                f"(messages={len(self._messages)}, "
                f"tokens={self._current_token_usage})"
            )

    def rollback(self) -> None:
        with self._lock:
            if self._snapshot is None:
                raise MemoryRollbackError(
                    "No snapshot available to restore."
                )

            self._sequence_counter = self._snapshot.sequence_counter
            self._current_token_usage = (
                self._snapshot.current_token_usage
            )
            self._scratchpad = dict(self._snapshot.scratchpad_state)
            self._messages = list(self._snapshot.messages_references)

            logger.warning(
                f"Memory rolled back successfully "
                f"(conversation={self.conversation_id})"
            )

            logger.info("Rollback completed successfully")

    def add_message(
        self,
        role: RoleEnum,
        content: Any,
        msg_type: MessageType = MessageType.CHAT,
        metadata: Optional[Metadata] = None,
        tool_calls: Optional[list[Metadata]] = None,
        tool_call_id: Optional[str] = None,
    ) -> Message:

        with self._lock:

            if not isinstance(role, RoleEnum):
                raise MemoryValidationError("Invalid role type.")

            if not isinstance(msg_type, MessageType):
                raise MemoryValidationError("Invalid message type.")

            tokens = self.token_counter.estimate(content)

            if (
                self._current_token_usage + tokens
                > self.max_token_limit
            ):
                if not settings.enable_auto_compression_on_overflow:
                    raise MemoryOverflowError(
                        f"Adding message exceeds token limit "
                        f"({self._current_token_usage + tokens} > "
                        f"{self.max_token_limit})"
                    )

            self._sequence_counter += 1

            msg = Message(
                conversation_id=self.conversation_id,
                message_id=str(uuid.uuid4()),
                sequence=self._sequence_counter,
                role=role,
                msg_type=msg_type,
                content=content,
                token_count=tokens,
                metadata=metadata or {},
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
            )

            self._messages.append(msg)
            self._current_token_usage += tokens

            logger.info(
                f"Added message seq={msg.sequence} "
                f"tokens={tokens}"
            )

            return msg

    def replace_messages(
        self,
        new_messages: Sequence[Message],
    ) -> None:

        with self._lock:

            seen_ids = set()
            seen_sequences = set()
            last_sequence = -1

            for msg in new_messages:

                if msg.token_count < 0:
                    raise MemoryValidationError(
                        f"Negative token count in "
                        f"{msg.message_id}"
                    )

                if msg.message_id in seen_ids:
                    raise MemoryValidationError(
                        f"Duplicate message id: "
                        f"{msg.message_id}"
                    )

                if msg.sequence in seen_sequences:
                    raise MemoryValidationError(
                        f"Duplicate sequence: "
                        f"{msg.sequence}"
                    )

                if msg.sequence < last_sequence:
                    raise MemoryValidationError(
                        f"Out of order sequence: "
                        f"{msg.sequence}"
                    )

                seen_ids.add(msg.message_id)
                seen_sequences.add(msg.sequence)
                last_sequence = msg.sequence

            self._messages = list(new_messages)

            self._current_token_usage = sum(
                (
                    m.token_count
                    if m.token_count > 0
                    else self.token_counter.estimate(m.content)
                )
                for m in new_messages
            )

            self._sequence_counter = max(
                (m.sequence for m in new_messages),
                default=0,
            )

            logger.info(
                f"Memory replaced successfully "
                f"({len(new_messages)} messages)"
            )

    def update_scratchpad(
        self,
        key: str,
        value: Any,
    ) -> None:

        with self._lock:
            self._scratchpad[key] = value

            logger.info(
                f"Scratchpad updated: {key}"
            )

    def get_scratchpad(self) -> Metadata:

        with self._lock:
            return dict(self._scratchpad)

    def clear_scratchpad(self) -> None:

        with self._lock:
            self._scratchpad.clear()

            logger.info("Scratchpad cleared.")

    def remove_scratchpad_key(
        self,
        key: str,
    ) -> None:

        with self._lock:
            self._scratchpad.pop(key, None)

            logger.info(
                f"Scratchpad key removed: {key}"
            )