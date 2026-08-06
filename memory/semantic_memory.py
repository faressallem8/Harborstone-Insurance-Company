from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging

from memory.schema import Message

logger = logging.getLogger("Harborstone.Memory")


class SemanticMemory:
    """
    Long-term semantic knowledge store.

    Supports:
    - Fact updating
    - Version history
    - Conflict resolution
    - Expiration
    """

    def __init__(self):
        self._facts: Dict[str, Message] = {}
        self._versions: Dict[str, List[Message]] = {}

    def add(self, message: Message):

        fact_key = message.metadata.get("fact_key")

        if not fact_key:
            logger.warning(
                "Semantic message ignored because no fact_key exists."
            )
            return

        existing = self._facts.get(fact_key)

        if existing is not None:

            logger.info(
                f"Conflict detected for '{fact_key}'. Updating latest fact."
            )

            self._versions.setdefault(
                fact_key,
                []
            ).append(existing)

        self._facts[fact_key] = message

        logger.info(
            f"Semantic fact stored: {fact_key}"
        )

    def extend(self, messages: List[Message]):

        for message in messages:
            self.add(message)

    def get(self, fact_key: str) -> Optional[Message]:

        return self._facts.get(fact_key)

    def get_versions(self, fact_key: str) -> List[Message]:

        return list(
            self._versions.get(fact_key, [])
        )

    def get_all(self) -> List[Message]:

        return list(self._facts.values())

    def remove(self, fact_key: str) -> bool:

        if fact_key not in self._facts:
            return False

        del self._facts[fact_key]

        logger.info(
            f"Removed semantic fact: {fact_key}"
        )

        return True

    def expire(self):

        now = datetime.now(timezone.utc)

        expired = []

        for key, message in self._facts.items():

            if (
                message.expires_at is not None
                and message.expires_at <= now
            ):
                expired.append(key)

        for key in expired:

            del self._facts[key]

            logger.info(
                f"Expired semantic fact: {key}"
            )

    def clear(self):

        self._facts.clear()
        self._versions.clear()

    def __len__(self):

        return len(self._facts)

    def __iter__(self):

        return iter(self._facts.values())