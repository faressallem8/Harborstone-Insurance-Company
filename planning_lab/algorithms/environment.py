import random

from ..models import EnvironmentFeedback


class Environment:
    """A stochastic evaluator biased toward favorable results."""

    def __init__(
        self,
        success_threshold: float = 0.6,
        rng: random.Random | None = None,
    ):
        if not 0.0 <= success_threshold <= 1.0:
            raise ValueError("success_threshold must be between zero and one")
        self.success_threshold = success_threshold
        self.rng = rng or random.Random()

    def evaluate(self, state: str) -> EnvironmentFeedback:
        del state  # This evaluator intentionally ignores the candidate contents.
        score = round(self.rng.betavariate(5.0, 2.0), 4)
        success = score >= self.success_threshold
        details = [] if success else ["The randomized evaluator rejected this attempt."]
        return EnvironmentFeedback(success=success, score=score, details=details)
