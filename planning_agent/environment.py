# planning_agent/environment.py
"""
Real EnvironmentFeedback for Harborstone Insurance.
Replaces the toolkit's randomized default with real MCP server calls.
"""

import json
from typing import Dict, Any, Optional
from mcp import ClientSession


class HarborstoneEnvironment:
    """
    Real environment that checks if a sub-task actually succeeded
    by calling the MCP server and validating results.
    """

    def __init__(self, session: ClientSession):
        self.session = session

    def evaluate(self, state: str) -> Dict[str, Any]:
        """
        Evaluate a candidate solution by calling real MCP tools.

        The toolkit's Environment interface expects evaluate() to return:
        {
            "success": bool,
            "score": float (0.0 - 1.0),
            "details": str
        }

        Args:
            state: A string representing the candidate solution or action

        Returns:
            Dict with success, score, and details
        """
        # Parse the state to extract the action
        try:
            # Try to parse as JSON
            data = json.loads(state)
            action_type = data.get("action")
            params = data.get("params", {})
        except (json.JSONDecodeError, TypeError):
            # If not JSON, treat as a raw action description
            action_type = "unknown"
            params = {"raw": state}

        try:
            if action_type == "fetch_claim":
                result = self._fetch_claim(params.get("claim_id", 1))
                return {
                    "success": True,
                    "score": 1.0,
                    "details": f"Claim fetched successfully: {result.get('claim_number', 'N/A')}"
                }

            elif action_type == "fetch_policy":
                result = self._fetch_policy(params.get("policy_id", 1))
                return {
                    "success": True,
                    "score": 1.0,
                    "details": f"Policy fetched successfully: {result.get('policy_number', 'N/A')}"
                }

            elif action_type == "fetch_customer":
                result = self._fetch_customer(params.get("customer_id", 1))
                return {
                    "success": True,
                    "score": 1.0,
                    "details": f"Customer fetched: {result.get('full_name', 'Unknown')}"
                }

            elif action_type == "make_decision":
                claim_id = params.get("claim_id", 1)
                decision = params.get("decision", "approved")
                result = self._make_decision(claim_id, decision)
                return {
                    "success": True,
                    "score": 1.0,
                    "details": f"Claim {claim_id} {decision}"
                }

            elif action_type == "check_fraud":
                result = self._check_fraud(params.get("claim_id", 1))
                if result.get("suspicious", False):
                    return {
                        "success": False,
                        "score": 0.2,
                        "details": f"Fraud detected: {result.get('reason', 'Unknown')}"
                    }
                return {
                    "success": True,
                    "score": 0.9,
                    "details": "No fraud detected"
                }

            else:
                return {
                    "success": False,
                    "score": 0.0,
                    "details": f"Unknown action type: {action_type}"
                }

        except Exception as e:
            return {
                "success": False,
                "score": 0.0,
                "details": f"Error: {str(e)}"
            }

    # ------------------------------
    # REAL MCP TOOL CALLS
    # ------------------------------

    def _fetch_claim(self, claim_id: int) -> Dict:
        """Call the MCP server's check_claim_status tool."""
        import asyncio
        result = asyncio.run_coroutine_threadsafe(
            self.session.call_tool("check_claim_status", arguments={"claim_id": claim_id}),
            asyncio.get_event_loop()
        ).result()
        return self._parse_result(result)

    def _fetch_policy(self, policy_id: int) -> Dict:
        """Call the MCP server's get_policy_details tool."""
        import asyncio
        result = asyncio.run_coroutine_threadsafe(
            self.session.call_tool("get_policy_details", arguments={"policy_id": policy_id}),
            asyncio.get_event_loop()
        ).result()
        return self._parse_result(result)

    def _fetch_customer(self, customer_id: int) -> Dict:
        """Call the MCP server's get_customer_info tool."""
        import asyncio
        result = asyncio.run_coroutine_threadsafe(
            self.session.call_tool("get_customer_info", arguments={"customer_id": customer_id}),
            asyncio.get_event_loop()
        ).result()
        return self._parse_result(result)

    def _make_decision(self, claim_id: int, decision: str) -> Dict:
        """Call the MCP server's approve_claim tool."""
        import asyncio
        result = asyncio.run_coroutine_threadsafe(
            self.session.call_tool(
                "approve_claim",
                arguments={"claim_id": claim_id, "decision": decision, "notes": "Planner agent decision"}
            ),
            asyncio.get_event_loop()
        ).result()
        return self._parse_result(result)

    def _check_fraud(self, claim_id: int) -> Dict:
        """Check for fraud using the database."""
        import pyodbc
        from mcp_server.server import get_db

        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                               SELECT COUNT(*)          as claim_count,
                                      AVG(claim_amount) as avg_amount
                               FROM Claims
                               WHERE policy_id = (SELECT policy_id FROM Claims WHERE claim_id = ?)
                                 AND claim_id != ?
                               """, (claim_id, claim_id))
                row = cursor.fetchone()

                claim_count = row[0] if row else 0

                if claim_count > 3:
                    return {
                        "suspicious": True,
                        "reason": f"Multiple claims ({claim_count}) on same policy",
                        "score": 0.1
                    }
                return {
                    "suspicious": False,
                    "reason": "No fraud indicators found",
                    "score": 0.9
                }
        except Exception as e:
            return {
                "suspicious": False,
                "reason": f"Could not check fraud: {e}",
                "score": 0.5
            }

    def _parse_result(self, result) -> Dict:
        """Parse MCP tool result into a dict."""
        if hasattr(result, "content"):
            for content in result.content:
                if hasattr(content, "text"):
                    try:
                        # Try to parse as JSON
                        parsed = json.loads(content.text)
                        return parsed
                    except:
                        # Return as text
                        return {"text": content.text}
        return {"raw": str(result)}