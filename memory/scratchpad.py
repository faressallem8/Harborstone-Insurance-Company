import threading
from typing import Any, Optional

from memory.types import Metadata


class Scratchpad:
    """
    Thread-safe temporary working memory.

    Stores transient state used during a conversation.
    """

    def __init__(self):
        self._data: Metadata = {}
        self._lock = threading.RLock()

    def set(
        self,
        key: str,
        value: Any,
    ) -> None:

        with self._lock:
            self._data[key] = value

    def get(
        self,
        key: str,
        default: Optional[Any] = None,
    ) -> Any:

        with self._lock:
            return self._data.get(key, default)

    def exists(
        self,
        key: str,
    ) -> bool:

        with self._lock:
            return key in self._data

    def delete(
        self,
        key: str,
    ) -> bool:

        with self._lock:
            return self._data.pop(key, None) is not None

    def clear(self) -> None:

        with self._lock:
            self._data.clear()

    def update(
        self,
        values: Metadata,
    ) -> None:

        with self._lock:
            self._data.update(values)

    def snapshot(self) -> Metadata:

        with self._lock:
            return dict(self._data)

    @property
    def size(self) -> int:

        with self._lock:
            return len(self._data)