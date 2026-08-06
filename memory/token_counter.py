from abc import ABC, abstractmethod
from typing import Any

from memory.exceptions import TokenizationError


class BaseTokenCounter(ABC):
    @abstractmethod
    def estimate(self, content: Any) -> int:
        """Fast approximate token counting."""
        pass

    @abstractmethod
    def exact(self, content: Any) -> int:
        """Exact model-specific token counting."""
        pass


class SimpleTokenCounter(BaseTokenCounter):
    """
    Lightweight heuristic token counter.

    Uses approximately 1 token per 4 characters.
    Suitable for development and testing.
    """

    def estimate(self, content: Any) -> int:

        if content is None:
            return 0

        try:
            text = str(content).strip()

            if not text:
                return 0

            # Approximate: 1 token ≈ 4 characters
            return max(1, (len(text) + 3) // 4)

        except Exception as exc:
            raise TokenizationError(
                f"Failed to estimate tokens: {exc}"
            ) from exc

    def exact(self, content: Any) -> int:

        raise TokenizationError(
            "Exact token counting requires a model-specific "
            "implementation (e.g. TikTokenCounter)."
        )