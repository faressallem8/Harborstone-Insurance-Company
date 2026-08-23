
"""
Appeal Graph - Multi-Day Claim Appeal Process with HITL and ToT.

Uses the REAL database schema:
- Claims table with status: Pending, Under Review, Approved, Rejected, Paid
- Claims have claim_id, policy_id, claim_amount, description
- Employees table for underwriter assignments
"""

import asyncio
import re
from typing import Dict, Any, Optional, List
from datetime import datetime

from state_graph.base_graph import BaseStateGraph
from state_graph.llm_additions import (
    tree_of_thoughts_search,
    constrained_react_step,
    rag_retrieve
)

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from mcp_server.server import call_tool


class AppealGraph(BaseStateGraph):
    """
    State graph for handling claim appeals.
    
    Database integration:
    - Claims: Read status, update to 'Under Review' or 'Approved'/'Rejected'
    - Employees: Assign underwriter for review
    - The graph uses REAL MCP tools to interact with the database
    """
    
    def __init__(self, agent_name: str = "appeal"):
        super().__init__(name="appeal_graph", agent_name=agent_name)
        self.claim_id = None
        self.appeal_id = None
    
    def define_graph(self) -> Dict[str, Any]:
        """Define the appeal graph structure."""
        return {
            "start": "start",
            "end": "end",
            "nodes": {
                "start": {
                    "handler": self._node_start,
                    "description": "Initialize appeal process"
                },
                "claim_denied": {
                    "handler": self._node_claim_denied,
                    "description": "Check if claim is REJECTED (database status)"
                },
                "appeal_started": {
                    "handler": self._node_appeal_started,
                    "description": "Create appeal record"
                },
                "appeal_strategy": {
                    "handler": self._node_appeal_strategy,
                    "description": "Select best strategy using Tree of Thoughts"
                },
                "awaiting_documents": {
                    "handler": self._node_awaiting_documents,
                    "description": "Wait for customer documents (HITL)"
                },
                "documents_received": {
                    "handler": self._node_documents_received,
                    "description": "Process received documents"
                },
                "submitting_appeal": {
                    "handler": self._node_submitting_appeal,
                    "description": "Submit appeal forms using Constrained ReAct"
                },
                "underwriter_review": {
                    "handler": self._node_underwriter_review,
                    "description": "Underwriter review (HITL)"
                },
                "appeal_approved": {
                    "handler": self._node_appeal_approved,
                    "description": "Appeal approved - update claim status"
                },
                "appeal_denied": {
                    "handler": self._node_appeal_denied,
                    "description": "Appeal denied - may escalate"
                },
                "escalated_to_manager": {
                    "handler": self._node_escalated_to_manager,
                    "description": "Manager review (HITL)"
                },
                "appeal_final_denied": {
                    "handler": self._node_appeal_final_denied,
                    "description": "Final appeal denial"
                },
                "end": {
                    "handler": self._node_end,
                    "description": "Appeal process complete"
                }
            },
            "edges": {
                "start": "claim_denied",
                "claim_denied": {
                    "default": "appeal_started",
                    "not_denied": "end"
                },
                "appeal_started": "appeal_strategy",
                "appeal_strategy": "awaiting_documents",
                "awaiting_documents": {
                    "documents_received": "documents_received",
                    "timeout": "end"
                },
                "documents_received": "submitting_appeal",
                "submitting_appeal": "underwriter_review",
                "underwriter_review": {
                    "approved": "appeal_approved",
                    "denied": "appeal_denied"
                },
                "appeal_approved": "end",
                "appeal_denied": {
                    "escalate": "escalated_to_manager",
                    "final": "appeal_final_denied"
                },
                "escalated_to_manager": {
                    "approved": "appeal_approved",
                    "denied": "appeal_final_denied"
                },
                "appeal_final_denied": "end",
                "end": "end"
            }
        }
    
    def get_hitl_conditions(self) -> List[str]:
        return [
            "awaiting_documents",
            "underwriter_review",
            "escalated_to_manager"
        ]
    
    def get_failure_conditions(self) -> List[str]:
        return [
            "awaiting_documents",
            "submitting_appeal",
            "underwriter_review"
        ]
    
    def get_node_timeout(self, node_name: str) -> Optional[int]:
        timeouts = {
            "awaiting_documents": 86400 * 3,
            "submitting_appeal": 300,
            "underwriter_review": 86400,
            "appeal_strategy": 30,
        }
        return timeouts.get(node_name)
    
    # ============================================================
    # NODE HANDLERS
    # ============================================================
    
    async def _node_start(self, state: Dict) -> Dict:
        """Initialize the appeal process."""
        claim_id = state.get("claim_id")
        if not claim_id:
            return {
                "error": "No claim_id provided",
                "next": "end"
            }
        
        self.claim_id = claim_id
        state["started_at"] = datetime.now().isoformat()
        state["status"] = "appeal_started"
        state["appeal_steps"] = []
        
        return {"next": "claim_denied"}
    
    async def _node_claim_denied(self, state: Dict) -> Dict:
        """
        Check if the claim is REJECTED (database status).
        
        Database status values: 'Pending', 'Under Review', 'Approved', 'Rejected', 'Paid'
        We only appeal claims that are 'Rejected'.
        """
        claim_id = state.get("claim_id")
        
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
            
            response = result.get("result", "")
            
            # Parse the claim status from the response string
            # Response format: "Status: Approved" or "Status: Rejected"
            status_match = re.search(r"Status:\s*(\w+)", response, re.IGNORECASE)
            if status_match:
                claim_status = status_match.group(1).strip()
                state["claim_status"] = claim_status
                state["claim_details"] = response
                
                # Database uses 'Rejected' (not 'Denied')
                if claim_status.lower() == "rejected":
                    state["appeal_steps"].append("claim_verified_rejected")
                    return {"next": "appeal_started"}
                else:
                    state["appeal_steps"].append("claim_not_rejected")
                    return {
                        "next": "end",
                        "error": f"Claim status is '{claim_status}' - cannot appeal (must be 'Rejected')"
                    }
            else:
                return {
                    "error": "Could not parse claim status from response",
                    "next": "end"
                }
                
        except Exception as e:
            return {
                "error": str(e),
                "next": "end"
            }
    
    async def _node_appeal_started(self, state: Dict) -> Dict:
        """Start the appeal process."""
        state["appeal_id"] = f"APP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        state["appeal_started_at"] = datetime.now().isoformat()
        state["status"] = "appeal_in_progress"
        state["appeal_steps"].append("appeal_initiated")
        
        return {"next": "appeal_strategy"}
    
    async def _node_appeal_strategy(self, state: Dict) -> Dict:
        """Select the best appeal strategy using Tree of Thoughts."""
        claim_id = state.get("claim_id")
        claim_details = state.get("claim_details", "Unknown claim details")
        
        # Get policy context using RAG
        rag_context = rag_retrieve(f"Claim denial and appeal policies for claim {claim_id}")
        policy_context = rag_context.get("answer", "")
        
        problem = f"""
        Claim #{claim_id} was REJECTED (database status: Rejected).
        
        Claim Details: {claim_details}
        
        Policy Context: {policy_context}
        
        Need to determine the best appeal strategy based on:
        1. The reason for rejection
        2. Policy coverage terms
        3. Supporting evidence available
        4. Likelihood of success on appeal
        5. Timeframe for appeal (30 days from rejection)
        
        Choose the best appeal approach from multiple strategies.
        """
        
        tot_result = await tree_of_thoughts_search(
            problem=problem,
            depth=3,
            beam_width=3
        )
        
        if tot_result.get("status") == "error":
            state["strategy_error"] = tot_result.get("error")
            state["strategy"] = "default"
            state["appeal_steps"].append("strategy_fallback_default")
        else:
            state["strategy"] = tot_result.get("best", "default")
            state["strategy_score"] = tot_result.get("best_score", 0.0)
            state["strategy_rationale"] = tot_result.get("thoughts", [])
            state["appeal_steps"].append("strategy_selected_via_tot")
        
        return {"next": "awaiting_documents"}
    
    async def _node_awaiting_documents(self, state: Dict) -> Dict:
        """Wait for customer documents (HITL pause)."""
        documents_needed = [
            "Claim rejection letter (from insurer)",
            "Supporting evidence (medical records, receipts)",
            "Policy documents showing coverage",
            "Expert opinion (if applicable)",
            "Any correspondence with insurer"
        ]
        
        state["documents_needed"] = documents_needed
        state["documents_received"] = []
        state["document_request_sent_at"] = datetime.now().isoformat()
        state["document_status"] = "pending"
        state["appeal_steps"].append("waiting_for_documents")
        
        return {"next": "awaiting_documents"}  # Will pause here
    
    async def _node_documents_received(self, state: Dict) -> Dict:
        """Process received documents."""
        received = state.get("documents_received", [])
        
        state["document_status"] = "received"
        state["documents_received_at"] = datetime.now().isoformat()
        state["document_count"] = len(received)
        state["appeal_steps"].append("documents_processed")
        
        return {"next": "submitting_appeal"}
    
    async def _node_submitting_appeal(self, state: Dict) -> Dict:
        """Submit appeal forms using Constrained ReAct."""
        claim_id = state.get("claim_id")
        appeal_id = state.get("appeal_id")
        strategy = state.get("strategy", "default")
        documents = state.get("documents_received", [])
        
        constraints = [
            "Use approved appeal form template",
            f"Include all {len(documents)} required documents",
            "Submit within 30 days of rejection",
            f"Justify the '{strategy}' strategy",
            "Do not exceed policy coverage limits",
            "Ensure all fields are completed",
            "Include customer signature"
        ]
        
        draft = f"""
        Appeal Submission for Claim #{claim_id}
        Appeal ID: {appeal_id}
        
        Strategy: {strategy}
        
        Documents Included:
        {chr(10).join(f'- {doc}' for doc in documents)}
        
        Justification: Based on the selected strategy, we believe this claim
        should be reconsidered because...
        """
        
        goal = f"Submit a complete appeal for claim #{claim_id} using the '{strategy}' strategy"
        
        react_result = await constrained_react_step(
            goal=goal,
            draft=draft,
            constraints=constraints
        )
        
        if react_result.get("status") == "error":
            state["submission_error"] = react_result.get("error")
            state["appeal_steps"].append("submission_failed")
            return {
                "error": react_result.get("error"),
                "next": "end"
            }
        
        state["submission_draft"] = react_result.get("original_draft")
        state["submission_revised"] = react_result.get("revised")
        state["submission_critique"] = react_result.get("critique")
        state["submission_improved"] = react_result.get("improved", False)
        state["submission_issues"] = react_result.get("grounded_issues", [])
        state["appeal_steps"].append("submission_completed_via_react")
        
        return {"next": "underwriter_review"}
    
    async def _node_underwriter_review(self, state: Dict) -> Dict:
        """Underwriter review (HITL pause)."""
        state["underwriter_review_started"] = datetime.now().isoformat()
        state["review_status"] = "pending"
        state["appeal_steps"].append("awaiting_underwriter_review")
        
        return {"next": "underwriter_review"}
    
    async def _node_appeal_approved(self, state: Dict) -> Dict:
        """
        Appeal approved - update claim status.
        
        In the database, we would update the claim status from 'Rejected' to 'Approved'
        using the MCP tool 'approve_claim'.
        """
        claim_id = state.get("claim_id")
        
        try:
            # Use the MCP tool to approve the claim
            result = await call_tool(
                agent_name=self.agent_name,
                tool_name="approve_claim",
                arguments={
                    "claim_id": claim_id,
                    "decision": "approved",
                    "notes": f"Appeal approved. Strategy: {state.get('strategy', 'default')}"
                }
            )
            
            if result.get("status") == "error":
                state["update_error"] = result.get("error")
                state["appeal_steps"].append("claim_update_failed")
            else:
                state["claim_updated"] = True
                state["appeal_steps"].append("claim_approved_via_mcp")
                
        except Exception as e:
            state["update_error"] = str(e)
            state["appeal_steps"].append("claim_update_exception")
        
        state["appeal_status"] = "approved"
        state["approved_at"] = datetime.now().isoformat()
        state["appeal_steps"].append("appeal_approved")
        
        return {"next": "end"}
    
    async def _node_appeal_denied(self, state: Dict) -> Dict:
        """Appeal denied - may escalate to manager."""
        state["appeal_status"] = "denied_by_underwriter"
        state["denied_at"] = datetime.now().isoformat()
        state["appeal_steps"].append("appeal_denied_by_underwriter")
        
        if state.get("escalation_available", True):
            return {"next": "escalated_to_manager"}
        else:
            return {"next": "appeal_final_denied"}
    
    async def _node_escalated_to_manager(self, state: Dict) -> Dict:
        """Manager review (HITL pause)."""
        state["escalated_at"] = datetime.now().isoformat()
        state["escalation_status"] = "pending"
        state["appeal_steps"].append("escalated_to_manager")
        
        return {"next": "escalated_to_manager"}
    
    async def _node_appeal_final_denied(self, state: Dict) -> Dict:
        """Final appeal denial."""
        state["appeal_status"] = "final_denied"
        state["final_denied_at"] = datetime.now().isoformat()
        state["appeal_steps"].append("appeal_final_denied")
        
        return {"next": "end"}
    
    async def _node_end(self, state: Dict) -> Dict:
        """End node - process complete."""
        state["completed_at"] = datetime.now().isoformat()
        state["status"] = "completed"
        state["appeal_steps"].append("process_completed")
        
        return {"next": "end"}