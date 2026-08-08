import json
import logging
from pathlib import Path
from typing import List, Optional

from memory.schema import Message

logger = logging.getLogger("Harborstone.Memory")


class EpisodicMemory:
    """
    Stores important conversation events with optional JSON persistence.
    """

    def __init__(self, persistence_file: Optional[Path] = None):
        self._episodes: List[Message] = []
        self.persistence_file = persistence_file
        if self.persistence_file and self.persistence_file.exists():
            self.load()

    def add(self, message: Message):
        self._episodes.append(message)
        logger.info(f"Episode stored: {message.message_id}")
        self.save()

    def extend(self, messages: List[Message]):
        for message in messages:
            self._episodes.append(message)
        logger.info(f"Extended episodic memory with {len(messages)} episodes.")
        self.save()

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
                logger.info(f"Episode removed: {message_id}")
                self.save()
                return True
        return False

    def clear(self):
        self._episodes.clear()
        logger.info("Episodic Memory cleared.")
        self.save()

    def save(self):
        if not self.persistence_file:
            return
        try:
            data = [msg.model_dump(mode="json") for msg in self._episodes]
            self.persistence_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("Episodic memory saved to disk.")
        except Exception as e:
            logger.error(f"Failed to save episodic memory: {e}")

    def load(self):
        if not self.persistence_file or not self.persistence_file.exists():
            return
        try:
            with open(self.persistence_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._episodes = [Message(**item) for item in data]
            logger.info(f"Loaded {len(self._episodes)} episodic memories from disk.")
        except Exception as e:
            logger.error(f"Failed to load episodic memory: {e}")

    def __len__(self):
        return len(self._episodes)

    def __iter__(self):
        return iter(self._episodes)

   