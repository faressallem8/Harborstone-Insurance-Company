from typing import List, Optional
import logging

from memory.schema import Message

logger = logging.getLogger("Harborstone.Memory")


class EpisodicMemory:
    """
    Stores important conversation events.
    """

    def __init__(self):
        self._episodes: List[Message] = []

    def add(self, message: Message):

        self._episodes.append(message)

        logger.info(
            f"Episode stored: {message.message_id}"
        )

    def extend(self, messages: List[Message]):

        for message in messages:
            self.add(message)

    def get_all(self) -> List[Message]:

        return list(self._episodes)

    def get_by_message_id(
        self,
        message_id: str,
    ) -> Optional[Message]:

        for message in self._episodes:

            if message.message_id == message_id:
                return message

        return None

    def remove(
        self,
        message_id: str,
    ) -> bool:

        for index, message in enumerate(self._episodes):

            if message.message_id == message_id:

                del self._episodes[index]

                logger.info(
                    f"Episode removed: {message_id}"
                )

                return True

        return False

    def clear(self):

        self._episodes.clear()

        logger.info("Episodic Memory cleared.")

    def __len__(self):

        return len(self._episodes)

    def __iter__(self):

        return iter(self._episodes)