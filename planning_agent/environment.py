# planning_agent/environment.py
"""
Real EnvironmentFeedback for Harborstone Insurance.
Now evaluates a candidate answer by comparing it with ground truth fetched from MCP.
"""

import json
import re
from typing import Dict, Any, Optional
from mcp import ClientSession
from planning_lab.models import EnvironmentFeedback


class HarborstoneEnvironment:
    def __init__(self, session: ClientSession):
        self.session = session

    async def evaluate(
        self,
        state: str,
        goal: Optional[str] = None,
    ) -> EnvironmentFeedback:
        """
        Evaluate a candidate answer (state) against the ground truth for the given goal.
        The goal is used to determine what data to fetch (policy, claim, customer, etc.)
        and then the state is checked for correctness.
        """
        if goal is None:
            # If no goal provided, treat the state as a plan description and fall back to heuristic
            return self._heuristic_evaluate(state)

        # 1. Parse the goal to extract entity IDs (policy_id, claim_id, customer_id)
        entities = self._extract_entities(goal)

        # 2. Fetch ground truth based on the extracted IDs
        ground_truth = {}
        try:
            if "policy_id" in entities:
                policy = await self._fetch_policy(entities["policy_id"])
                ground_truth["policy"] = policy
            if "claim_id" in entities:
                claim = await self._fetch_claim(entities["claim_id"])
                ground_truth["claim"] = claim
            if "customer_id" in entities:
                customer = await self._fetch_customer(entities["customer_id"])
                ground_truth["customer"] = customer
        except Exception as e:
            return EnvironmentFeedback(
                success=False,
                score=0.0,
                feedback=f"Failed to fetch ground truth: {e}",
                details={"error": str(e), "goal": goal}
            )

        if not ground_truth:
            # If no entities could be extracted, fall back to heuristic
            return self._heuristic_evaluate(state)

        # 3. Compare the candidate state with the ground truth
        feedback, score = self._compare_with_ground_truth(state, ground_truth)

        return EnvironmentFeedback(
            success=score >= 0.7,
            score=round(score, 2),
            feedback=feedback,
            details={"ground_truth": ground_truth, "goal": goal}
        )

    # ------------------ Helper Methods ------------------

    def _extract_entities(self, goal: str) -> Dict[str, int]:
        """Extract policy_id, claim_id, customer_id from the goal text."""
        entities = {}
        # Policy: look for "policy" followed by a number
        policy_match = re.search(r'policy\s*[#:]*\s*(\d+)', goal, re.IGNORECASE)
        if policy_match:
            entities["policy_id"] = int(policy_match.group(1))
        # Claim: look for "claim" followed by a number
        claim_match = re.search(r'claim\s*[#:]*\s*(\d+)', goal, re.IGNORECASE)
        if claim_match:
            entities["claim_id"] = int(claim_match.group(1))
        # Customer: look for "customer" followed by a number
        customer_match = re.search(r'customer\s*[#:]*\s*(\d+)', goal, re.IGNORECASE)
        if customer_match:
            entities["customer_id"] = int(customer_match.group(1))
        return entities

    async def _fetch_policy(self, policy_id: int) -> Dict:
        result = await self.session.call_tool(
            "get_policy_details",
            arguments={"policy_id": policy_id}
        )
        return self._parse_result(result)

    async def _fetch_claim(self, claim_id: int) -> Dict:
        result = await self.session.call_tool(
            "check_claim_status",
            arguments={"claim_id": claim_id}
        )
        return self._parse_result(result)

    async def _fetch_customer(self, customer_id: int) -> Dict:
        result = await self.session.call_tool(
            "get_customer_info",
            arguments={"customer_id": customer_id}
        )
        return self._parse_result(result)

    def _parse_result(self, result) -> Dict:
        if hasattr(result, "content"):
            for content in result.content:
                if hasattr(content, "text"):
                    try:
                        return json.loads(content.text)
                    except:
                        return {"text": content.text}
        return {"raw": str(result)}

    def _compare_with_ground_truth(self, state: str, ground_truth: Dict) -> tuple[str, float]:
        """
        Compare the candidate answer (state) with the ground truth data.
        Returns a feedback string and a score (0.0-1.0).
        """
        state_lower = state.lower()
        matches = 0
        total = 0

        # Check policy fields if present
        if "policy" in ground_truth:
            policy = ground_truth["policy"]
            # Convert dict to key:value pairs for checking
            for key, value in policy.items():
                if isinstance(value, (str, int, float)):
                    total += 1
                    if str(value).lower() in state_lower:
                        matches += 1

        # Check claim fields
        if "claim" in ground_truth:
            claim = ground_truth["claim"]
            for key, value in claim.items():
                if isinstance(value, (str, int, float)):
                    total += 1
                    if str(value).lower() in state_lower:
                        matches += 1

        # Check customer fields
        if "customer" in ground_truth:
            customer = ground_truth["customer"]
            for key, value in customer.items():
                if isinstance(value, (str, int, float)):
                    total += 1
                    if str(value).lower() in state_lower:
                        matches += 1

        if total == 0:
            return "No ground truth fields to compare against.", 0.0

        score = matches / total
        feedback = f"Matched {matches} out of {total} key facts."

        # Additional check: if the goal asks for a decision (approve/deny) we can check that
        if "approve" in state_lower or "deny" in state_lower:
            # Very basic: if the state contains a decision, give a small bonus
            if "approve" in state_lower or "deny" in state_lower:
                # But we can't know if it's correct without a true decision; we just check presence
                pass

        return feedback, score

    def _heuristic_evaluate(self, state: str) -> EnvironmentFeedback:
        """Fallback heuristic (same as the ungrounded environment but simpler)."""
        text = state.lower()
        score = 0.4
        feedback = []
        if len(text) > 80:
            score += 0.15
            feedback.append("Detailed response.")
        keywords = ["claim", "policy", "customer", "risk", "approve", "coverage"]
        matches = sum(k in text for k in keywords)
        score += min(matches * 0.08, 0.35)
        if matches:
            feedback.append("Uses relevant insurance terminology.")
        if re.search(r"\b\d+\b", text):
            score += 0.1
            feedback.append("Contains identifiers.")
        score = min(score, 0.95)
        return EnvironmentFeedback(
            success=score >= 0.65,
            score=round(score, 2),
            feedback=" ".join(feedback) or "Looks reasonable.",
            details={"evaluation": "heuristic"}
        )