
"""
Renewal Graph - Policy Renewal with External Data Wait and RAG.

This graph handles the complete policy renewal process:
1. Customer requests policy renewal
2. Agent fetches vessel inspection report (may take 24-72 hours)
3. Agent assesses risk using RAG guidelines
4. If risk unchanged → auto-renew
5. If risk changed → underwriter review (HITL)

HITL nodes:
- underwriter_review: If risk has changed significantly

Ticket nodes:
- await_inspection_report: If inspection times out
- risk_assessment: If RAG fails

Uses REAL database schema:
- InsurancePolicies: policy_id, status, coverage_amount, start_date, end_date
- Vessels: vessel_id, vessel_name, vessel_type, year_built, insured_value
- Customers: customer_id, full_name, email
"""

import asyncio
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from state_graph.base_graph import BaseStateGraph
from state_graph.llm_additions import (
    rag_retrieve,              # REAL RAG from RAG/
    decompose_task,            # REAL decomposition from planning_lab
    tree_of_thoughts_search    # REAL ToT from planning_lab (for risk analysis)
)

import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from mcp_server.server import call_tool


class RenewalGraph(BaseStateGraph):
    """
    State graph for handling policy renewals.
    
    Database integration:
    - InsurancePolicies: Read policy details, update status to 'Active'
    - Vessels: Get vessel information for risk assessment
    - The graph uses REAL MCP tools to interact with the database
    """
    
    def __init__(self, agent_name: str = "renewal"):
        super().__init__(name="renewal_graph", agent_name=agent_name)
        self.policy_id = None
        self.renewal_id = None
    
    # ============================================================
    # GRAPH DEFINITION - Nodes and Edges
    # ============================================================
    
    def define_graph(self) -> Dict[str, Any]:
        """
        Define the renewal graph structure.
        
        The graph flows through:
        1. Start → Initialize renewal
        2. Fetch policy and vessel details
        3. Wait for inspection report (may take 24-72 hours)
        4. If report received → assess risk with RAG
        5. If report times out → create ticket
        6. If risk unchanged → auto-renew
        7. If risk changed → underwriter review (HITL)
        8. Complete renewal
        """
        return {
            "start": "start",
            "end": "end",
            "nodes": {
                "start": {
                    "handler": self._node_start,
                    "description": "Initialize renewal process"
                },
                "renewal_started": {
                    "handler": self._node_renewal_started,
                    "description": "Start renewal and fetch policy details"
                },
                "fetch_vessel_details": {
                    "handler": self._node_fetch_vessel_details,
                    "description": "Get vessel information from policy"
                },
                "decompose_renewal": {
                    "handler": self._node_decompose_renewal,
                    "description": "Decompose renewal into sub-tasks using Task Decomposition"
                },
                "await_inspection_report": {
                    "handler": self._node_await_inspection_report,
                    "description": "Wait for vessel inspection report (external API)"
                },
                "report_received": {
                    "handler": self._node_report_received,
                    "description": "Process received inspection report"
                },
                "report_timeout": {
                    "handler": self._node_report_timeout,
                    "description": "Inspection report timed out - create ticket"
                },
                "risk_assessment": {
                    "handler": self._node_risk_assessment,
                    "description": "Assess risk using RAG + ToT"
                },
                "auto_renew": {
                    "handler": self._node_auto_renew,
                    "description": "Auto-renew policy (no risk change)"
                },
                "underwriter_review": {
                    "handler": self._node_underwriter_review,
                    "description": "Underwriter review for risk change (HITL)"
                },
                "renewal_approved": {
                    "handler": self._node_renewal_approved,
                    "description": "Renewal approved by underwriter"
                },
                "renewal_denied": {
                    "handler": self._node_renewal_denied,
                    "description": "Renewal denied by underwriter"
                },
                "end": {
                    "handler": self._node_end,
                    "description": "Renewal process complete"
                }
            },
            "edges": {
                "start": "renewal_started",
                "renewal_started": "fetch_vessel_details",
                "fetch_vessel_details": "decompose_renewal",
                "decompose_renewal": "await_inspection_report",
                "await_inspection_report": {
                    "received": "report_received",
                    "timeout": "report_timeout"
                },
                "report_received": "risk_assessment",
                "report_timeout": "end",  # Creates a ticket
                "risk_assessment": {
                    "auto": "auto_renew",
                    "review": "underwriter_review"
                },
                "auto_renew": "end",
                "underwriter_review": {
                    "approved": "renewal_approved",
                    "denied": "renewal_denied"
                },
                "renewal_approved": "end",
                "renewal_denied": "end",
                "end": "end"
            }
        }
    
    # ============================================================
    # HITL AND FAILURE CONDITIONS
    # ============================================================
    
    def get_hitl_conditions(self) -> List[str]:
        """Nodes that require human-in-the-loop approval."""
        return [
            "underwriter_review"  # Underwriter must review if risk changed
        ]
    
    def get_failure_conditions(self) -> List[str]:
        """Nodes where failures create tickets."""
        return [
            "await_inspection_report",  # Timeout → inspection API failed
            "risk_assessment",           # RAG failed
            "report_timeout"             # Explicit timeout node
        ]
    
    def get_node_timeout(self, node_name: str) -> Optional[int]:
        """
        Timeout in seconds for specific nodes.
        
        The inspection report can take 24-72 hours (configurable).
        """
        timeouts = {
            "await_inspection_report": 86400 * 3,  # 3 days
            "risk_assessment": 60,                  # 1 minute for RAG
            "underwriter_review": 86400,            # 1 day for underwriter
            "decompose_renewal": 30,                # 30 seconds for decomposition
        }
        return timeouts.get(node_name)
    
    # ============================================================
    # NODE HANDLERS
    # ============================================================
    
    async def _node_start(self, state: Dict) -> Dict:
        """Initialize the renewal process."""
        policy_id = state.get("policy_id")
        if not policy_id:
            return {
                "error": "No policy_id provided",
                "next": "end"
            }
        
        self.policy_id = policy_id
        state["started_at"] = datetime.now().isoformat()
        state["status"] = "renewal_started"
        state["renewal_steps"] = []
        
        return {"next": "renewal_started"}
    
    async def _node_renewal_started(self, state: Dict) -> Dict:
        """
        Start renewal and fetch policy details using MCP tool.
        
        Uses the REAL get_policy_details tool from mcp_server.
        The response is a formatted string that we parse.
        """
        policy_id = state.get("policy_id")
        
        try:
            result = await call_tool(
                agent_name=self.agent_name,
                tool_name="get_policy_details",
                arguments={"policy_id": policy_id}
            )
            
            if result.get("status") == "error":
                return {
                    "error": result.get("error"),
                    "next": "end"
                }
            
            response = result.get("result", "")
            state["policy_details_raw"] = response
            
            # Parse policy details from the response string
            # Response format: 
            # "Policy ID: 1\nPolicy Number: POL001\nCustomer: John Smith\nVessel: Ocean Spirit\n..."
            policy_data = self._parse_policy_details(response)
            state.update(policy_data)
            state["policy_fetched_at"] = datetime.now().isoformat()
            state["renewal_steps"].append("policy_fetched")
            
            return {"next": "fetch_vessel_details"}
            
        except Exception as e:
            return {
                "error": str(e),
                "next": "end"
            }
    
    def _parse_policy_details(self, response: str) -> Dict[str, Any]:
        """
        Parse the policy details response string.
        
        Example response:
        POLICY DETAILS
        Policy ID: 1
        Policy Number: POL001
        Customer: John Smith
        Vessel: Ocean Spirit
        Type: Marine Cargo
        Coverage: $5,000,000.00
        Deductible: $50,000.00
        Premium: $120,000.00
        Start Date: 2025-01-01
        End Date: 2025-12-31
        Status: ACTIVE
        """
        data = {}
        patterns = {
            "policy_id": r"Policy ID:\s*(\d+)",
            "policy_number": r"Policy Number:\s*(\S+)",
            "customer_name": r"Customer:\s*(.+)",
            "vessel_name": r"Vessel:\s*(.+)",
            "policy_type": r"Type:\s*(.+)",
            "coverage_amount": r"Coverage:\s*\$([\d,]+\.?\d*)",
            "deductible": r"Deductible:\s*\$([\d,]+\.?\d*)",
            "premium": r"Premium:\s*\$([\d,]+\.?\d*)",
            "start_date": r"Start Date:\s*(\d{4}-\d{2}-\d{2})",
            "end_date": r"End Date:\s*(\d{4}-\d{2}-\d{2})",
            "status": r"Status:\s*(\w+)",
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if key in ["coverage_amount", "deductible", "premium"]:
                    try:
                        data[key] = float(value.replace(",", ""))
                    except:
                        data[key] = value
                else:
                    data[key] = value
        
        return data
    
    async def _node_fetch_vessel_details(self, state: Dict) -> Dict:
        """
        Get vessel information from the policy.
        
        The vessel name is already in the policy details.
        For more details, we could call a vessel-specific MCP tool.
        """
        vessel_name = state.get("vessel_name", "")
        policy_type = state.get("policy_type", "Unknown")
        coverage_amount = state.get("coverage_amount", 0)
        
        state["vessel_details"] = {
            "vessel_name": vessel_name,
            "vessel_type": policy_type,
            "insured_value": coverage_amount,
        }
        
        state["renewal_steps"].append("vessel_details_fetched")
        
        return {"next": "decompose_renewal"}
    
    async def _node_decompose_renewal(self, state: Dict) -> Dict:
        """
        Decompose the renewal process into sub-tasks.
        
        This uses the REAL decompose_task() from planning_lab.
        It breaks the renewal into parallel subtasks:
        1. Fetch policy details
        2. Fetch vessel information
        3. Check inspection report
        4. Assess risk
        5. Generate renewal recommendation
        """
        policy_id = state.get("policy_id")
        vessel_name = state.get("vessel_name", "Unknown")
        
        goal = f"""
        Complete policy renewal for policy #{policy_id} on vessel '{vessel_name}'.
        
        Steps:
        1. Verify policy is eligible for renewal
        2. Check vessel inspection status
        3. Assess risk
        4. Determine if auto-renew or underwriter review
        5. Complete renewal process
        """
        
        decomposition_result = await decompose_task(
            goal=goal,
            max_tasks=5
        )
        
        if decomposition_result.get("status") == "error":
            state["decomposition_error"] = decomposition_result.get("error")
            state["renewal_steps"].append("decomposition_fallback")
            # Fallback: use a simple task list
            state["tasks"] = [
                {"id": "t1", "instruction": "Fetch policy details", "depends_on": []},
                {"id": "t2", "instruction": "Check vessel inspection", "depends_on": []},
                {"id": "t3", "instruction": "Assess risk", "depends_on": ["t1", "t2"]},
                {"id": "t4", "instruction": "Generate renewal decision", "depends_on": ["t3"]},
            ]
        else:
            state["decomposition_plan"] = decomposition_result.get("plan")
            state["tasks"] = decomposition_result.get("tasks", [])
            state["renewal_steps"].append("decomposition_completed")
        
        return {"next": "await_inspection_report"}
    
    async def _node_await_inspection_report(self, state: Dict) -> Dict:
        """
        Wait for vessel inspection report.
        
        This simulates waiting for an external API response.
        The report can take 24-72 hours to arrive.
        
        In a real system, this would:
        1. Call an external inspection API
        2. Store the request ID
        3. Poll for completion or wait for webhook
        
        The HITL system will mark the report as received via the web_platform.
        """
        state["inspection_requested_at"] = datetime.now().isoformat()
        state["inspection_status"] = "pending"
        state["inspection_expected_by"] = (
            datetime.now() + timedelta(days=3)
        ).isoformat()
        state["renewal_steps"].append("waiting_for_inspection")
        
        # This will cause the graph to pause. The admin will:
        # 1. Either mark the report as received → go to report_received
        # 2. Or let it timeout → go to report_timeout (creates ticket)
        return {"next": "await_inspection_report"}
    
    async def _node_report_received(self, state: Dict) -> Dict:
        """Process the received inspection report."""
        # The report is received via webhook or HITL resolution
        report_data = state.get("inspection_report", {})
        
        state["inspection_status"] = "received"
        state["inspection_received_at"] = datetime.now().isoformat()
        state["inspection_findings"] = report_data.get("findings", "")
        state["vessel_condition"] = report_data.get("condition", "good")
        state["risk_factors"] = report_data.get("risk_factors", [])
        state["renewal_steps"].append("inspection_report_received")
        
        return {"next": "risk_assessment"}
    
    async def _node_report_timeout(self, state: Dict) -> Dict:
        """
        Handle inspection report timeout - creates a ticket.
        
        The graph will pause here and the admin can:
        1. Manually enter the inspection data
        2. Request the inspection again
        3. Cancel the renewal
        """
        state["inspection_status"] = "timeout"
        state["timeout_at"] = datetime.now().isoformat()
        state["renewal_steps"].append("inspection_timeout_ticket_created")
        
        return {
            "error": "Inspection report timeout after 3 days",
            "next": "end"  # This will create a ticket via failure_nodes
        }
    
    async def _node_risk_assessment(self, state: Dict) -> Dict:
        """
        Assess risk using RAG + Tree of Thoughts.
        
        This uses:
        1. RAG to retrieve underwriting guidelines from the database
        2. ToT to analyze risk scenarios
        3. Policy data to determine if renewal is safe
        
        The risk assessment determines if the policy can auto-renew
        or needs underwriter review.
        """
        vessel_name = state.get("vessel_name", "Unknown")
        vessel_type = state.get("vessel_type", "Unknown")
        coverage_amount = state.get("coverage_amount", 0)
        vessel_condition = state.get("vessel_condition", "good")
        risk_factors = state.get("risk_factors", [])
        
        # ============================================================
        # Step 1: Use RAG to get underwriting guidelines
        # ============================================================
        
        rag_query = f"""
        Underwriting guidelines for vessel renewal:
        Vessel: {vessel_name}
        Type: {vessel_type}
        Condition: {vessel_condition}
        Coverage Amount: ${coverage_amount:,.2f}
        Risk Factors: {', '.join(risk_factors) if risk_factors else 'None'}
        
        What are the renewal criteria and risk assessment factors?
        """
        
        rag_result = rag_retrieve(rag_query)
        guidelines = rag_result.get("answer", "Standard renewal guidelines apply.")
        sources = rag_result.get("sources", [])
        
        state["risk_guidelines"] = guidelines
        state["risk_sources"] = sources
        
        # ============================================================
        # Step 2: Use Tree of Thoughts for risk analysis
        # ============================================================
        
        tot_problem = f"""
        Risk assessment for policy renewal:
        
        Vessel: {vessel_name} ({vessel_type})
        Current Coverage: ${coverage_amount:,.2f}
        Vessel Condition: {vessel_condition}
        Risk Factors: {', '.join(risk_factors) if risk_factors else 'None'}
        
        Underwriting Guidelines:
        {guidelines[:500]}...
        
        Should this policy be:
        1. Auto-renewed (no significant risk change)
        2. Sent for underwriter review (significant risk change)
        
        Consider:
        - Vessel condition
        - Claims history
        - Market conditions
        - Regulatory requirements
        - Risk factors identified
        """
        
        tot_result = await tree_of_thoughts_search(
            problem=tot_problem,
            depth=2,
            beam_width=2
        )
        
        state["risk_analysis"] = tot_result.get("thoughts", [])
        
        # ============================================================
        # Step 3: Calculate risk score
        # ============================================================
        
        # Start with base score
        risk_score = 0.3  # Low base
        
        # Adjust based on risk factors
        if risk_factors:
            risk_score += len(risk_factors) * 0.1
        
        # Adjust based on vessel condition
        if vessel_condition == "poor":
            risk_score += 0.4
        elif vessel_condition == "fair":
            risk_score += 0.2
        elif vessel_condition == "good":
            risk_score += 0.0
        elif vessel_condition == "excellent":
            risk_score -= 0.1
        
        # Adjust based on vessel age (from policy type)
        current_year = datetime.now().year
        year_built = state.get("year_built")
        if year_built:
            vessel_age = current_year - year_built
            if vessel_age > 20:
                risk_score += 0.3
            elif vessel_age > 10:
                risk_score += 0.1
        
        # Adjust based on coverage amount
        if coverage_amount > 5000000:
            risk_score += 0.2
        elif coverage_amount > 2000000:
            risk_score += 0.1
        
        # Normalize
        risk_score = min(max(risk_score, 0.0), 1.0)
        state["risk_score"] = risk_score
        state["risk_level"] = (
            "Low" if risk_score < 0.4 else
            "Medium" if risk_score < 0.7 else
            "High"
        )
        state["renewal_steps"].append("risk_assessment_completed")
        
        # ============================================================
        # Step 4: Determine next action
        # ============================================================
        
        # Auto-renew if risk is low or medium-low
        if risk_score < 0.5:
            state["renewal_decision"] = "auto_renew"
            state["renewal_steps"].append("decision_auto_renew")
            return {"next": "auto_renew"}
        else:
            state["renewal_decision"] = "underwriter_review"
            state["renewal_steps"].append("decision_underwriter_review")
            return {"next": "underwriter_review"}
    
    async def _node_auto_renew(self, state: Dict) -> Dict:
        """
        Auto-renew policy.
        
        In the database, this would update the policy status and extend the end_date.
        The policy status would change from 'Active' to 'Active' (renewed)
        and the end_date would be extended by 1 year.
        """
        policy_id = state.get("policy_id")
        policy_number = state.get("policy_number", "Unknown")
        current_end_date = state.get("end_date")
        
        # Calculate new end date (1 year from current end date)
        try:
            if current_end_date:
                end_date = datetime.strptime(current_end_date, "%Y-%m-%d")
                new_end_date = end_date.replace(year=end_date.year + 1)
                state["new_end_date"] = new_end_date.strftime("%Y-%m-%d")
            else:
                state["new_end_date"] = (
                    datetime.now() + timedelta(days=365)
                ).strftime("%Y-%m-%d")
        except:
            state["new_end_date"] = (
                datetime.now() + timedelta(days=365)
            ).strftime("%Y-%m-%d")
        
        state["renewal_status"] = "auto_renewed"
        state["renewed_at"] = datetime.now().isoformat()
        state["renewal_steps"].append("policy_auto_renewed")
        
        # Note: In production, we would call an MCP tool to update the policy
        # await call_tool(
        #     agent_name=self.agent_name,
        #     tool_name="update_policy",
        #     arguments={
        #         "policy_id": policy_id,
        #         "end_date": state["new_end_date"],
        #         "status": "Active"
        #     }
        # )
        
        return {"next": "end"}
    
    async def _node_underwriter_review(self, state: Dict) -> Dict:
        """
        Underwriter review (HITL pause).
        
        The graph pauses here and waits for the underwriter to:
        1. Approve the renewal → go to renewal_approved
        2. Deny the renewal → go to renewal_denied
        3. Request changes → stay in this state
        """
        state["underwriter_review_started"] = datetime.now().isoformat()
        state["review_status"] = "pending"
        state["renewal_steps"].append("awaiting_underwriter_review")
        
        return {"next": "underwriter_review"}
    
    async def _node_renewal_approved(self, state: Dict) -> Dict:
        """Renewal approved by underwriter."""
        policy_id = state.get("policy_id")
        
        # Calculate new end date
        current_end_date = state.get("end_date")
        try:
            if current_end_date:
                end_date = datetime.strptime(current_end_date, "%Y-%m-%d")
                new_end_date = end_date.replace(year=end_date.year + 1)
                state["new_end_date"] = new_end_date.strftime("%Y-%m-%d")
            else:
                state["new_end_date"] = (
                    datetime.now() + timedelta(days=365)
                ).strftime("%Y-%m-%d")
        except:
            state["new_end_date"] = (
                datetime.now() + timedelta(days=365)
            ).strftime("%Y-%m-%d")
        
        state["renewal_status"] = "approved_by_underwriter"
        state["approved_at"] = datetime.now().isoformat()
        state["renewal_steps"].append("renewal_approved")
        
        return {"next": "end"}
    
    async def _node_renewal_denied(self, state: Dict) -> Dict:
        """Renewal denied by underwriter."""
        state["renewal_status"] = "denied_by_underwriter"
        state["denied_at"] = datetime.now().isoformat()
        state["renewal_steps"].append("renewal_denied")
        
        return {"next": "end"}
    
    async def _node_end(self, state: Dict) -> Dict:
        """End node - process complete."""
        state["completed_at"] = datetime.now().isoformat()
        state["status"] = "completed"
        state["renewal_steps"].append("process_completed")
        
        return {"next": "end"}