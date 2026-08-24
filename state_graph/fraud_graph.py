"""
Fraud Graph - Fraud Investigation with Cross-Department Escalation.

This graph handles the complete fraud investigation process:
1. A claim is flagged for potential fraud
2. Claims department reviews the claim
3. If suspicious → underwriter review (HITL)
4. If still suspicious → legal review (HITL)
5. Final decision: fraud confirmed or cleared

HITL nodes:
- claims_review: Claims officer reviews initial findings
- underwriting_review: Underwriter reviews suspicious claims
- legal_review: Legal department reviews high-risk cases

Ticket nodes:
- fraud_flagged: If fraud check system fails
- claims_review: If claims review fails
- underwriting_review: If underwriter system fails

Uses REAL database schema:
- Claims: claim_id, status, amount, description
- FraudChecks: claim_id, fraud_score, fraud_status, checked_by
- Employees: employee_id, role_name, full_name
"""

import asyncio
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from state_graph.base_graph import BaseStateGraph
from state_graph.llm_additions import (
    lats_search,  # REAL LATS from planning_lab
    constrained_react_step,  # REAL self_refine from planning_lab
    rag_retrieve  # REAL RAG from RAG/
)

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from mcp_server.server import call_tool


class FraudGraph(BaseStateGraph):
    """
    State graph for handling fraud investigations.

    Database integration:
    - Claims: Read claim details
    - FraudChecks: Read/write fraud status
    - Employees: Assign investigators
    - The graph uses REAL MCP tools to interact with the database
    """

    def __init__(self, agent_name: str = "fraud"):
        super().__init__(name="fraud_graph", agent_name=agent_name)
        self.claim_id = None
        self.fraud_check_id = None

    # ============================================================
    # GRAPH DEFINITION - Nodes and Edges
    # ============================================================

    def define_graph(self) -> Dict[str, Any]:
        """
        Define the fraud investigation graph structure.

        The graph flows through:
        1. Start → Claim flagged for fraud
        2. Claims department reviews (HITL)
        3. If cleared → end
        4. If suspicious → Underwriter reviews (HITL)
        5. If cleared → end
        6. If still suspicious → Legal reviews (HITL)
        7. Final decision: fraud confirmed or cleared
        """
        return {
            "start": "start",
            "end": "end",
            "nodes": {
                "start": {
                    "handler": self._node_start,
                    "description": "Initialize fraud investigation"
                },
                "fraud_flagged": {
                    "handler": self._node_fraud_flagged,
                    "description": "Claim flagged for potential fraud"
                },
                "claims_review": {
                    "handler": self._node_claims_review,
                    "description": "Claims department review (HITL)"
                },
                "fraud_cleared": {
                    "handler": self._node_fraud_cleared,
                    "description": "Fraud cleared - no further action"
                },
                "underwriting_review": {
                    "handler": self._node_underwriting_review,
                    "description": "Underwriter review (HITL)"
                },
                "legal_review": {
                    "handler": self._node_legal_review,
                    "description": "Legal department review (HITL)"
                },
                "fraud_confirmed": {
                    "handler": self._node_fraud_confirmed,
                    "description": "Fraud confirmed - escalate"
                },
                "end": {
                    "handler": self._node_end,
                    "description": "Investigation complete"
                }
            },
            "edges": {
                "start": "fraud_flagged",
                "fraud_flagged": "claims_review",
                "claims_review": {
                    "cleared": "fraud_cleared",
                    "suspicious": "underwriting_review"
                },
                "fraud_cleared": "end",
                "underwriting_review": {
                    "cleared": "fraud_cleared",
                    "suspicious": "legal_review"
                },
                "legal_review": {
                    "cleared": "fraud_cleared",
                    "confirmed": "fraud_confirmed"
                },
                "fraud_confirmed": "end",
                "end": "end"
            }
        }

    # ============================================================
    # HITL AND FAILURE CONDITIONS
    # ============================================================

    def get_hitl_conditions(self) -> List[str]:
        """Nodes that require human-in-the-loop approval."""
        return [
            "claims_review",  # Claims officer reviews
            "underwriting_review",  # Underwriter reviews
            "legal_review"  # Legal department reviews
        ]

    def get_failure_conditions(self) -> List[str]:
        """Nodes where failures create tickets."""
        return [
            "fraud_flagged",  # Fraud check system failed
            "claims_review",  # Claims review failed
            "underwriting_review",  # Underwriter system failed
            "legal_review"  # Legal system failed
        ]

    def get_node_timeout(self, node_name: str) -> Optional[int]:
        """Timeout in seconds for specific nodes."""
        timeouts = {
            "claims_review": 86400,  # 1 day
            "underwriting_review": 86400,  # 1 day
            "legal_review": 86400 * 2,  # 2 days
            "fraud_flagged": 60,  # 1 minute for fraud check
        }
        return timeouts.get(node_name)

    # ============================================================
    # LATS EVALUATOR FUNCTIONS
    # ============================================================

    async def _evaluate_investigation_order(self, state: str) -> Dict[str, Any]:
        """
        Evaluator for LATS - scores investigation orderings.

        This is called by LATS to evaluate different investigation orders.
        A good investigation order:
        - Checks the most suspicious items first
        - Follows logical progression
        - Minimizes wasted effort
        """
        # Parse the state to extract the investigation order
        # The state is a string describing the order

        score = 0.5  # Base score

        # Check for key indicators
        if "fraud score" in state.lower():
            score += 0.1
        if "policy" in state.lower():
            score += 0.1
        if "evidence" in state.lower():
            score += 0.1
        if "interview" in state.lower():
            score += 0.1

        # Penalty for missing key steps
        if "review" not in state.lower():
            score -= 0.2

        # Normalize
        score = min(max(score, 0.0), 1.0)

        return {
            "success": score > 0.5,
            "score": score,
            "details": f"Investigation order scored {score:.2f}"
        }

    # ============================================================
    # NODE HANDLERS
    # ============================================================

    async def _node_start(self, state: Dict) -> Dict:
        """Initialize the fraud investigation."""
        claim_id = state.get("claim_id")
        if not claim_id:
            return {
                "error": "No claim_id provided",
                "next": "end"
            }

        self.claim_id = claim_id
        state["started_at"] = datetime.now().isoformat()
        state["status"] = "fraud_investigation_started"
        state["fraud_steps"] = []
        state["investigation_level"] = 0  # 0=initial, 1=underwriting, 2=legal

        return {"next": "fraud_flagged"}

    async def _node_fraud_flagged(self, state: Dict) -> Dict:
        """
        Claim flagged for potential fraud.

        This uses:
        1. RAG to get fraud detection patterns
        2. LATS to search over investigation strategies
        3. Constrained ReAct to execute the investigation
        """
        claim_id = state.get("claim_id")

        # ============================================================
        # Step 1: Get claim details
        # ============================================================

        try:
            result = await call_tool(
                agent_name=self.agent_name,
                tool_name="check_claim_status",
                arguments={"claim_id": claim_id}
            )

            if result.get("status") == "error":
                return {
                    "error": result.get("error"),
                    "next": "end"
                }

            state["claim_details"] = result.get("result", "")

        except Exception as e:
            return {
                "error": str(e),
                "next": "end"
            }

        # ============================================================
        # Step 2: Use RAG to get fraud detection patterns
        # ============================================================

        rag_result = rag_retrieve(f"Fraud detection patterns and red flags for marine insurance claims")
        state["fraud_patterns"] = rag_result.get("answer", "")
        state["fraud_sources"] = rag_result.get("sources", [])

        # ============================================================
        # Step 3: Use LATS to search over investigation strategies
        # ============================================================

        lats_task = f"""
        Investigate claim #{claim_id} for potential fraud.

        Claim Details: {state['claim_details']}

        Fraud Patterns: {state['fraud_patterns']}

        Find the best investigation order to detect fraud.
        """

        lats_result = await lats_search(
            task=lats_task,
            evaluator_func=self._evaluate_investigation_order,
            iterations=3,
            n_actions=3
        )

        state["lats_result"] = lats_result
        state["investigation_strategy"] = lats_result.get("output", "")
        state["investigation_score"] = lats_result.get("best_score", 0.0)
        state["fraud_steps"].append("lats_investigation_completed")

        # ============================================================
        # Step 4: Use Constrained ReAct to execute investigation
        # ============================================================

        constraints = [
            "Only use approved investigation methods",
            "Must maintain chain of custody for evidence",
            "Must document all findings",
            "Must respect customer privacy",
            "Must follow compliance guidelines"
        ]

        react_result = await constrained_react_step(
            goal=f"Execute fraud investigation for claim #{claim_id}",
            draft=state["investigation_strategy"],
            constraints=constraints
        )

        state["investigation_plan"] = react_result.get("revised", "")
        state["investigation_issues"] = react_result.get("grounded_issues", [])
        state["fraud_steps"].append("investigation_planned_via_react")

        # ============================================================
        # Step 5: Determine initial fraud risk
        # ============================================================

        # Parse claim amount for risk assessment
        amount_match = re.search(r"Amount:\s*\$([\d,]+\.?\d*)", state['claim_details'])
        if amount_match:
            try:
                claim_amount = float(amount_match.group(1).replace(",", ""))
                state["claim_amount"] = claim_amount
            except:
                state["claim_amount"] = 0

        # Parse claim status
        status_match = re.search(r"Status:\s*(\w+)", state['claim_details'], re.IGNORECASE)
        if status_match:
            state["claim_status"] = status_match.group(1).strip()

        # Estimate fraud risk based on LATS score
        lats_score = state.get("investigation_score", 0.0)

        if lats_score > 0.7:
            state["fraud_risk"] = "High"
        elif lats_score > 0.4:
            state["fraud_risk"] = "Medium"
        else:
            state["fraud_risk"] = "Low"

        state["fraud_steps"].append("initial_fraud_risk_assessed")

        return {"next": "claims_review"}

    async def _node_claims_review(self, state: Dict) -> Dict:
        """
        Claims department review (HITL).

        This is the first HITL pause. The claims officer reviews the fraud flags.

        The claims officer can:
        1. Clear the fraud → go to fraud_cleared
        2. Flag as suspicious → go to underwriting_review
        """
        state["claims_review_started"] = datetime.now().isoformat()
        state["review_level"] = "claims"
        state["fraud_steps"].append("awaiting_claims_review")

        decision = state.get("hitl_decision", {}) or {}
        if decision:
            outcome = decision.get("outcome") or ("cleared" if decision.get("approved", True) else "suspicious")
            state["review_status"] = "resolved"
            state["claims_review_resolved_at"] = datetime.now().isoformat()
            state["fraud_steps"].append(f"claims_review_resolved_{outcome}")
            return {"next": "fraud_cleared" if outcome == "cleared" else "underwriting_review"}

        state["review_status"] = "pending"
        return {"next": "claims_review"}  # Will pause here (first pass, pre-HITL)

    async def _node_fraud_cleared(self, state: Dict) -> Dict:
        """
        Fraud cleared - no further action.

        The claim has been cleared of fraud suspicion.
        Update the fraud status in the database.
        """
        state["fraud_status"] = "cleared"
        state["cleared_at"] = datetime.now().isoformat()
        state["cleared_by"] = state.get("hitl_decision", {}).get("reviewer", "Unknown")
        state["cleared_reason"] = state.get("hitl_decision", {}).get("reason", "No fraud found")
        state["fraud_steps"].append("fraud_cleared")

        # In production, we would update the FraudChecks table
        # await call_tool(
        #     agent_name=self.agent_name,
        #     tool_name="update_fraud_check",
        #     arguments={
        #         "claim_id": self.claim_id,
        #         "fraud_status": "Clear",
        #         "checked_by": state["cleared_by"]
        #     }
        # )

        return {"next": "end"}

    async def _node_underwriting_review(self, state: Dict) -> Dict:
        """
        Underwriter review (HITL).

        This is the second HITL pause. The underwriter reviews suspicious claims.

        The underwriter can:
        1. Clear the fraud → go to fraud_cleared
        2. Still suspicious → go to legal_review
        """
        state["underwriting_review_started"] = datetime.now().isoformat()
        state["review_level"] = "underwriting"
        state["investigation_level"] = 1
        state["fraud_steps"].append("awaiting_underwriting_review")

        decision = state.get("hitl_decision", {}) or {}
        if decision:
            outcome = decision.get("outcome") or ("cleared" if decision.get("approved", True) else "suspicious")
            state["review_status"] = "resolved"
            state["underwriting_review_resolved_at"] = datetime.now().isoformat()
            state["fraud_steps"].append(f"underwriting_review_resolved_{outcome}")
            return {"next": "fraud_cleared" if outcome == "cleared" else "legal_review"}

        state["review_status"] = "pending"
        return {"next": "underwriting_review"}  # Will pause here (first pass, pre-HITL)

    async def _node_legal_review(self, state: Dict) -> Dict:
        """
        Legal department review (HITL).

        This is the final HITL pause. Legal reviews high-risk cases.

        Legal can:
        1. Clear the fraud → go to fraud_cleared
        2. Confirm fraud → go to fraud_confirmed
        """
        state["legal_review_started"] = datetime.now().isoformat()
        state["review_level"] = "legal"
        state["investigation_level"] = 2
        state["fraud_steps"].append("awaiting_legal_review")

        decision = state.get("hitl_decision", {}) or {}
        if decision:
            outcome = decision.get("outcome") or ("cleared" if decision.get("approved", True) else "confirmed")
            state["review_status"] = "resolved"
            state["legal_review_resolved_at"] = datetime.now().isoformat()
            state["fraud_steps"].append(f"legal_review_resolved_{outcome}")
            return {"next": "fraud_cleared" if outcome == "cleared" else "fraud_confirmed"}

        state["review_status"] = "pending"
        return {"next": "legal_review"}  # Will pause here (first pass, pre-HITL)

    async def _node_fraud_confirmed(self, state: Dict) -> Dict:
        """
        Fraud confirmed - escalate.

        Fraud has been confirmed by legal department.
        This would trigger:
        1. Update claim status to 'Rejected' if not already
        2. Record fraud in FraudChecks table
        3. Alert fraud team
        4. Potentially refer to authorities
        """
        claim_id = state.get("claim_id")
        decision = state.get("hitl_decision", {})

        state["fraud_status"] = "confirmed"
        state["confirmed_at"] = datetime.now().isoformat()
        state["confirmed_by"] = decision.get("reviewer", "Unknown")
        state["fraud_evidence"] = decision.get("evidence", "")
        state["fraud_steps"].append("fraud_confirmed")

        # In production, we would update the claim status and fraud check
        # Update claim status to 'Rejected'
        # await call_tool(
        #     agent_name=self.agent_name,
        #     tool_name="approve_claim",
        #     arguments={
        #         "claim_id": claim_id,
        #         "decision": "rejected",
        #         "notes": f"Fraud confirmed. Evidence: {state['fraud_evidence']}"
        #     }
        # )

        return {"next": "end"}

    async def _node_end(self, state: Dict) -> Dict:
        """End node - investigation complete."""
        state["completed_at"] = datetime.now().isoformat()
        state["status"] = "completed"
        state["fraud_steps"].append("investigation_completed")

        return {"next": "end"}