import re

from planning_lab.models import EnvironmentFeedback


class UngroundedEnvironmentAdapter:

    async def evaluate(self, state: str) -> EnvironmentFeedback:

        text = state.lower()

        score = 0.4
        feedback = []

        # Looks structured
        if len(text) > 80:
            score += 0.15
            feedback.append("Detailed response.")

        # Mentions common insurance concepts
        keywords = [
            "claim",
            "policy",
            "customer",
            "risk",
            "approve",
            "coverage",
        ]

        matches = sum(k in text for k in keywords)
        score += min(matches * 0.08, 0.35)

        if matches:
            feedback.append("Uses relevant insurance terminology.")

        # Looks like it contains an identifier
        if re.search(r"\b\d+\b", text):
            score += 0.1
            feedback.append("Contains identifiers.")

        score = min(score, 0.95)

        return EnvironmentFeedback(
            success=score >= 0.65,
            score=round(score, 2),
            feedback=" ".join(feedback) or "Looks reasonable.",
            details={
                "evaluation": "ungrounded heuristic",
                "matched_keywords": matches,
            },
        )