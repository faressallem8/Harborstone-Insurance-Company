# planning_agent/environment.py
"""
Real EnvironmentFeedback for Harborstone Insurance.
Replaces the toolkit's randomized default with real MCP server calls.
"""

import json
from typing import Dict, Any
import asyncio
from mcp import ClientSession
from planning_lab.models import EnvironmentFeedback


class HarborstoneEnvironment:
    def __init__(self, session: ClientSession):
        self.session = session

    def evaluate(
        self,
        state: str,
        goal: str | None = None,
    ) -> EnvironmentFeedback:
        """
        Evaluate a candidate state against the real Harborstone system.

        Parameters
        ----------
        state:
            Candidate output produced by the planning algorithm.

        goal:
            Optional original task. Used by grounded critique
            (e.g. Self-Refine) but ignored by LATS when not provided.
        """
        # Parse the state
        try:
            data = json.loads(state)
            action_type = data.get("action")
            params = data.get("params", {})
        except (json.JSONDecodeError, TypeError):
            action_type = "unknown"
            params = {"raw": state}
            import re
            if "claim" in state.lower():
                match = re.search(r'claim_id["\s:=]+(\d+)', state, re.IGNORECASE)
                if match:
                    action_type = "fetch_claim"
                    params = {"claim_id": int(match.group(1))}
            elif "approve" in state.lower():
                action_type = "make_decision"
                params = {"claim_id": 1, "decision": "approved"}

        try:
            if action_type == "fetch_claim":
                result = self._fetch_claim(params.get("claim_id", 1))
                return EnvironmentFeedback(
                    success=True,
                    score=1.0,
                    feedback="Claim information was successfully retrieved.",
                    details={
                        "claim": result,
                        "goal": goal,
                    }
                )
            elif action_type == "fetch_policy":
                result = self._fetch_policy(params.get("policy_id", 1))
                return EnvironmentFeedback(
                    success=True,
                    score=1.0,
                    feedback="Policy information was successfully retrieved.",
                    details={
                        "policy": result,
                        "goal": goal,
                    }
                )
            elif action_type == "fetch_customer":
                result = self._fetch_customer(params.get("customer_id", 1))
                return EnvironmentFeedback(
                    success=True,
                    score=1.0,
                    feedback="Customer information was successfully retrieved.",
                    details={
                        "customer": result,
                        "goal": goal,
                    }
                )
            elif action_type == "make_decision":
                claim_id = params.get("claim_id", 1)
                decision = params.get("decision", "approved")
                result = self._make_decision(claim_id, decision)
                return EnvironmentFeedback(
                    success=True,
                    score=1.0,
                    feedback=f"Claim {claim_id} was {decision}.",
                    details={
                        "decision": result,
                        "goal": goal,
                    }
                )
            elif action_type == "check_fraud":
                result = self._check_fraud(params.get("claim_id", 1))
                if result.get("suspicious", False):
                    return EnvironmentFeedback(
                        success=False,
                        score=0.2,
                        feedback="Fraud indicators were detected.",
                        details={
                            "fraud_result": result,
                            "goal": goal,
                        }
                    )
                return EnvironmentFeedback(
                    success=True,
                    score=0.9,
                    feedback="No fraud indicators were detected.",
                    details={
                        "fraud_result": result,
                        "goal": goal,
                    }
                )
            else:
                return EnvironmentFeedback(
                    success=False,
                    score=0.0,
                    feedback=f"Unsupported action '{action_type}'.",
                    details={
                        "action": action_type,
                        "goal": goal,
                    }
                )
        except Exception as e:
            return EnvironmentFeedback(
                success=False,
                score=0.0,
                feedback="Environment evaluation failed.",
                details={
                    "error": str(e),
                    "goal": goal,
                }
            )

    # ------------------------------
    # REAL MCP TOOL CALLS (synchronous)
    # ------------------------------

    def _fetch_claim(self, claim_id: int) -> Dict:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.session.call_tool("check_claim_status", arguments={"claim_id": claim_id})
            )
        finally:
            loop.close()
        return self._parse_result(result)

    def _fetch_policy(self, policy_id: int) -> Dict:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.session.call_tool("get_policy_details", arguments={"policy_id": policy_id})
            )
        finally:
            loop.close()
        return self._parse_result(result)

    def _fetch_customer(self, customer_id: int) -> Dict:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.session.call_tool("get_customer_info", arguments={"customer_id": customer_id})
            )
        finally:
            loop.close()
        return self._parse_result(result)

    def _make_decision(self, claim_id: int, decision: str) -> Dict:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.session.call_tool(
                    "approve_claim",
                    arguments={"claim_id": claim_id, "decision": decision, "notes": "Planner agent decision"}
                )
            )
        finally:
            loop.close()
        return self._parse_result(result)

    def _check_fraud(self, claim_id: int) -> Dict:
        import pyodbc
        from mcp_server.server import get_db
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM Claims
                    WHERE policy_id = (SELECT policy_id FROM Claims WHERE claim_id = ?)
                    AND claim_id != ?
                """, (claim_id, claim_id))
                row = cursor.fetchone()
                count = row[0] if row else 0
                if count > 3:
                    return {"suspicious": True, "reason": f"Multiple claims ({count})"}
                return {"suspicious": False, "reason": "No fraud indicators"}
        except Exception as e:
            return {"suspicious": False, "reason": f"Check error: {e}"}

    def _parse_result(self, result) -> Dict:
        if hasattr(result, "content"):
            for content in result.content:
                if hasattr(content, "text"):
                    try:
                        return json.loads(content.text)
                    except:
                        return {"text": content.text}
        return {"raw": str(result)}