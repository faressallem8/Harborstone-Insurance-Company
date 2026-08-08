import uuid
import threading
import logging
from collections.abc import Sequence
from typing import Any, Optional

from memory.schema import (
    Message,
    MessageType,
    RoleEnum,
    Scratchpad,
    ShortTermMemorySnapshot,
)
from memory.token_counter import (
    BaseTokenCounter,
    SimpleTokenCounter,
)
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
            max_token_limit
            if max_token_limit is not None
            else settings.default_max_token_limit
        )

        self.token_counter = (
            token_counter
            if token_counter is not None
            else SimpleTokenCounter()
        )

        # =========================================================
        # SHORT-TERM MESSAGE BUFFER
        # =========================================================

        self._messages: list[Message] = []

        self._current_token_usage: int = 0

        self._sequence_counter: int = 0

        # =========================================================
        # STRUCTURED SCRATCHPAD
        #
        # IMPORTANT:
        # Scratchpad is intentionally separate from the message
        # transcript.
        #
        # Context pruning can remove messages without destroying
        # the agent's current goal, plan, sub-goal, or working state.
        # =========================================================

        self._scratchpad: Scratchpad = Scratchpad()

        # =========================================================
        # THREAD SAFETY
        # =========================================================

        self._lock = threading.RLock()

        # =========================================================
        # SNAPSHOT / ROLLBACK
        # =========================================================

        self._snapshot: Optional[
            ShortTermMemorySnapshot
        ] = None

    # =============================================================
    # MESSAGE ACCESS
    # =============================================================

    def get_read_snapshot_messages(
        self,
    ) -> tuple[Message, ...]:

        with self._lock:
            return tuple(self._messages)

    def get_messages(
        self,
    ) -> tuple[Message, ...]:

        with self._lock:
            return tuple(self._messages)

    @property
    def current_token_usage(self) -> int:

        with self._lock:
            return self._current_token_usage

    @property
    def message_count(self) -> int:

        with self._lock:
            return len(self._messages)

    # =============================================================
    # SCRATCHPAD ACCESS
    # =============================================================

    def get_scratchpad(self) -> Scratchpad:

        """
        Return a copy of the current structured scratchpad.

        The caller receives a model copy rather than the internal
        object, preventing accidental mutation of STM state.
        """

        with self._lock:
            return self._scratchpad.model_copy(
                deep=True
            )

    def update_scratchpad(
        self,
        key: str,
        value: Any,
    ) -> None:

        """
        Backward-compatible generic scratchpad update.

        Supported keys:

            goal
            plan
            current_subgoal
            completed_steps
            working_state

        For working_state, the value should be a dictionary.
        """

        with self._lock:

            if key == "goal":

                self._scratchpad.goal = (
                    None
                    if value is None
                    else str(value)
                )

            elif key == "plan":

                if not isinstance(value, list):
                    raise MemoryValidationError(
                        "Scratchpad 'plan' must be a list."
                    )

                self._scratchpad.plan = [
                    str(item)
                    for item in value
                ]

            elif key == "current_subgoal":

                self._scratchpad.current_subgoal = (
                    None
                    if value is None
                    else str(value)
                )

            elif key == "completed_steps":

                if not isinstance(value, list):
                    raise MemoryValidationError(
                        "Scratchpad 'completed_steps' "
                        "must be a list."
                    )

                self._scratchpad.completed_steps = [
                    str(item)
                    for item in value
                ]

            elif key == "working_state":

                if not isinstance(value, dict):
                    raise MemoryValidationError(
                        "Scratchpad 'working_state' "
                        "must be a dictionary."
                    )

                self._scratchpad.working_state = dict(
                    value
                )

            else:

                raise MemoryValidationError(
                    f"Unknown scratchpad key: {key}"
                )

            self._touch_scratchpad()

            logger.info(
                f"Scratchpad updated: {key}"
            )

    # =============================================================
    # STRUCTURED SCRATCHPAD API
    # =============================================================

    def set_goal(
        self,
        goal: Optional[str],
    ) -> None:

        with self._lock:

            self._scratchpad.goal = (
                None
                if goal is None
                else str(goal)
            )

            self._touch_scratchpad()

            logger.info(
                f"Scratchpad goal updated: {goal}"
            )

    def get_goal(self) -> Optional[str]:

        with self._lock:
            return self._scratchpad.goal

    def set_plan(
        self,
        plan: Sequence[str],
    ) -> None:

        with self._lock:

            self._scratchpad.plan = [
                str(step)
                for step in plan
            ]

            self._touch_scratchpad()

            logger.info(
                f"Scratchpad plan updated "
                f"(steps={len(self._scratchpad.plan)})"
            )

    def get_plan(self) -> list[str]:

        with self._lock:
            return list(
                self._scratchpad.plan
            )

    def set_current_subgoal(
        self,
        subgoal: Optional[str],
    ) -> None:

        with self._lock:

            self._scratchpad.current_subgoal = (
                None
                if subgoal is None
                else str(subgoal)
            )

            self._touch_scratchpad()

            logger.info(
                f"Scratchpad current sub-goal updated: "
                f"{subgoal}"
            )

    def get_current_subgoal(
        self,
    ) -> Optional[str]:

        with self._lock:
            return self._scratchpad.current_subgoal

    def add_completed_step(
        self,
        step: str,
    ) -> None:

        with self._lock:

            self._scratchpad.completed_steps.append(
                str(step)
            )

            self._touch_scratchpad()

            logger.info(
                f"Scratchpad completed step added: {step}"
            )

    def get_completed_steps(self) -> list[str]:

        with self._lock:
            return list(
                self._scratchpad.completed_steps
            )

    def update_working_state(
        self,
        key: str,
        value: Any,
    ) -> None:

        with self._lock:

            self._scratchpad.working_state[
                key
            ] = value

            self._touch_scratchpad()

            logger.info(
                f"Scratchpad working state updated: "
                f"{key}"
            )

    def get_working_state(self) -> Metadata:

        with self._lock:

            return dict(
                self._scratchpad.working_state
            )

    def replace_working_state(
        self,
        state: Metadata,
    ) -> None:

        with self._lock:

            self._scratchpad.working_state = dict(
                state
            )

            self._touch_scratchpad()

            logger.info(
                "Scratchpad working state replaced."
            )

    def clear_scratchpad(self) -> None:

        with self._lock:

            self._scratchpad = Scratchpad()

            logger.info(
                "Scratchpad cleared."
            )

    def remove_scratchpad_key(
        self,
        key: str,
    ) -> None:

        """
        Backward-compatible helper.

        Removes a value from the appropriate structured
        scratchpad field.
        """

        with self._lock:

            if key == "goal":

                self._scratchpad.goal = None

            elif key == "plan":

                self._scratchpad.plan = []

            elif key == "current_subgoal":

                self._scratchpad.current_subgoal = None

            elif key == "completed_steps":

                self._scratchpad.completed_steps = []

            elif key == "working_state":

                self._scratchpad.working_state = {}

            else:

                raise MemoryValidationError(
                    f"Unknown scratchpad key: {key}"
                )

            self._touch_scratchpad()

            logger.info(
                f"Scratchpad key removed: {key}"
            )

    def _touch_scratchpad(self) -> None:

        """
        Update the scratchpad timestamp whenever its state changes.
        """

        # Pydantic model fields are mutable, so updating the
        # timestamp explicitly keeps the state traceable.
        from datetime import datetime, timezone

        self._scratchpad.last_updated = (
            datetime.now(timezone.utc)
        )

    # =============================================================
    # SNAPSHOT
    # =============================================================

    def create_snapshot(self) -> None:

        with self._lock:

            self._snapshot = ShortTermMemorySnapshot(
                sequence_counter=self._sequence_counter,
                current_token_usage=(
                    self._current_token_usage
                ),
                scratchpad_state=(
                    self._scratchpad.model_dump(
                        mode="python"
                    )
                ),
                messages_references=list(
                    self._messages
                ),
            )

            logger.info(
                f"Snapshot created "
                f"(messages={len(self._messages)}, "
                f"tokens={self._current_token_usage})"
            )

    # =============================================================
    # ROLLBACK
    # =============================================================

    def rollback(self) -> None:

        with self._lock:

            if self._snapshot is None:

                raise MemoryRollbackError(
                    "No snapshot available to restore."
                )

            self._sequence_counter = (
                self._snapshot.sequence_counter
            )

            self._current_token_usage = (
                self._snapshot.current_token_usage
            )

            # Restore structured scratchpad.
            scratchpad_state = (
                self._snapshot.scratchpad_state
            )

            self._scratchpad = Scratchpad(
                **scratchpad_state
            )

            self._messages = list(
                self._snapshot.messages_references
            )

            logger.warning(
                f"Memory rolled back successfully "
                f"(conversation={self.conversation_id})"
            )

            logger.info(
                "Rollback completed successfully."
            )

    # =============================================================
    # ADD MESSAGE
    # =============================================================

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

            if not isinstance(
                role,
                RoleEnum,
            ):

                raise MemoryValidationError(
                    "Invalid role type."
                )

            if not isinstance(
                msg_type,
                MessageType,
            ):

                raise MemoryValidationError(
                    "Invalid message type."
                )

            tokens = self.token_counter.estimate(
                content
            )

            projected_usage = (
                self._current_token_usage
                + tokens
            )

            if (
                projected_usage
                > self.max_token_limit
            ):

                if not settings.enable_auto_compression_on_overflow:

                    raise MemoryOverflowError(
                        f"Adding message exceeds token "
                        f"limit "
                        f"({projected_usage} > "
                        f"{self.max_token_limit})"
                    )

                # IMPORTANT:
                #
                # Auto compression is NOT performed here.
                #
                # Context management strategies live in
                # context_eval / context management layer.
                #
                # We only log the overflow so the caller can
                # invoke the selected pruning strategy.
                logger.warning(
                    f"STM token limit reached: "
                    f"{projected_usage} > "
                    f"{self.max_token_limit}. "
                    f"Context manager should prune before "
                    f"adding more context."
                )

            # -----------------------------------------------------
            # Sequence
            # -----------------------------------------------------

            self._sequence_counter += 1

            msg = Message(
                conversation_id=(
                    self.conversation_id
                ),
                message_id=str(
                    uuid.uuid4()
                ),
                sequence=(
                    self._sequence_counter
                ),
                role=role,
                msg_type=msg_type,
                content=content,
                token_count=tokens,
                metadata=metadata or {},
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
            )

            # -----------------------------------------------------
            # Store message
            # -----------------------------------------------------

            self._messages.append(msg)

            self._current_token_usage += tokens

            logger.info(
                f"Added message "
                f"seq={msg.sequence} "
                f"tokens={tokens} "
                f"total_tokens={self._current_token_usage}"
            )

            return msg

    # =============================================================
    # REPLACE MESSAGES
    # =============================================================

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

                seen_ids.add(
                    msg.message_id
                )

                seen_sequences.add(
                    msg.sequence
                )

                last_sequence = msg.sequence

            # -----------------------------------------------------
            # Replace transcript ONLY.
            #
            # Scratchpad intentionally remains untouched.
            # -----------------------------------------------------

            self._messages = list(
                new_messages
            )

            self._current_token_usage = sum(
                (
                    m.token_count
                    if m.token_count > 0
                    else self.token_counter.estimate(
                        m.content
                    )
                )
                for m in new_messages
            )

            self._sequence_counter = max(
                (
                    m.sequence
                    for m in new_messages
                ),
                default=0,
            )

            logger.info(
                f"Memory transcript replaced successfully "
                f"({len(new_messages)} messages, "
                f"{self._current_token_usage} tokens). "
                f"Scratchpad preserved."
            )

    # =============================================================
    # REMOVE MESSAGE
    # =============================================================

    def remove_message(
        self,
        message_id: str,
    ) -> bool:

        with self._lock:

            for index, message in enumerate(
                self._messages
            ):

                if message.message_id == message_id:

                    del self._messages[index]

                    self._current_token_usage = sum(
                        (
                            m.token_count
                            if m.token_count > 0
                            else self.token_counter.estimate(
                                m.content
                            )
                        )
                        for m in self._messages
                    )

                    logger.info(
                        f"Message removed: "
                        f"{message_id}"
                    )

                    return True

            return False

    # =============================================================
    # CLEAR MESSAGES
    # =============================================================

    def clear_messages(self) -> None:

        with self._lock:

            self._messages.clear()

            self._current_token_usage = 0

            logger.info(
                "Short-Term Memory messages cleared. "
                "Scratchpad preserved."
            )

    # =============================================================
    # CLEAR EVERYTHING
    # =============================================================

    def clear(self) -> None:

        with self._lock:

            self._messages.clear()

            self._current_token_usage = 0

            self._sequence_counter = 0

            self._scratchpad = Scratchpad()

            self._snapshot = None

            logger.info(
                "Short-Term Memory completely cleared."
            )