from typing import Dict, List, Optional
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

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
    - JSON Persistence
    """

    def __init__(self, persistence_file: Optional[Path] = None):
        self._facts: Dict[str, Message] = {}
        self._versions: Dict[str, List[Message]] = {}
        self.persistence_file = persistence_file
        if self.persistence_file and self.persistence_file.exists():
            self.load()

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
        self.save()

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
        self.save()

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

        if expired:
            self.save()

    def clear(self):
        self._facts.clear()
        self._versions.clear()
        self.save()

    def save(self):
        if not self.persistence_file:
            return
        try:
            data = {
                "facts": {
                    key: msg.model_dump(mode="json")
                    for key, msg in self._facts.items()
                },
                "versions": {
                    key: [msg.model_dump(mode="json") for msg in msg_list]
                    for key, msg_list in self._versions.items()
                },
            }
            self.persistence_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("Semantic memory saved to disk.")
        except Exception as e:
            logger.error(f"Failed to save semantic memory: {e}")

    def load(self):
        if not self.persistence_file or not self.persistence_file.exists():
            return
        try:
            with open(self.persistence_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._facts = {
                k: Message(**v) for k, v in data.get("facts", {}).items()
            }
            self._versions = {
                k: [Message(**item) for item in v_list]
                for k, v_list in data.get("versions", {}).items()
            }
            logger.info(
                f"Loaded {len(self._facts)} semantic facts from disk."
            )
        except Exception as e:
            logger.error(f"Failed to load semantic memory: {e}")

    def __len__(self):
        return len(self._facts)

    def __iter__(self):
        return iter(self._facts.values())
    def search(self, query: str) -> List[Message]:
        """
        Search semantic facts by matching query substring against fact_key or content.
        """
        query_lower = query.lower()
        results = []
        for key, msg in self._facts.items():
            content = getattr(msg, "content", None)
            if isinstance(content, list):
                content_str = " ".join(str(item) for item in content).lower()
            elif content is not None:
                content_str = str(content).lower()
            else:
                content_str = ""
            
            if query_lower in key.lower() or query_lower in content_str:
                results.append(msg)
        
        return results if results else self.get_all()