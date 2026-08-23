
"""
Base State Graph with Checkpointing, HITL, and Ticket Support.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable, Awaitable, Union
from datetime import datetime
from enum import Enum
import uuid

# Import web_platform database functions for persistence
from web_platform.database import (
    save_checkpoint as db_save_checkpoint,
    get_checkpoint as db_get_checkpoint,
    get_latest_checkpoint as db_get_latest_checkpoint,
)


class GraphStatus(str, Enum):
    """Status of a graph run - for tracking where we are"""
    RUNNING = "running"
    PAUSED = "paused"      # HITL pause - waiting for human
    FAILED = "failed"      # Ticket created - unplanned failure
    COMPLETED = "completed"


class BaseStateGraph(ABC):
    """
    Abstract base class for state graphs.
    
    This implements the core pattern:
    - Nodes: units of work
    - Edges: routing logic (deterministic, not emergent)
    - State: typed dict that nodes read/write
    - Checkpoints: persisted after each node for crash recovery
    
    Three things every graph needs:
    1. define_graph(): What are the nodes and edges?
    2. get_hitl_conditions(): Where do we pause for humans?
    3. get_failure_conditions(): Where do failures create tickets?
    """
    
    def __init__(self, name: str, agent_name: str):
        self.name = name
        self.agent_name = agent_name
        
        # The three primitives
        self.nodes: Dict[str, Callable] = {}      # Node handlers (functions only!)
        self.edges: Dict[str, Union[str, Dict, List]] = {}  # Routing
        self.state: Dict[str, Any] = {}           # Current state
        
        # Runtime tracking
        self.run_id: Optional[str] = None
        self.current_node: Optional[str] = None
        self.status: GraphStatus = GraphStatus.RUNNING
        self._max_iterations = 50  # Prevent infinite loops
        self._iteration_count = 0
    
    # ============================================================
    # ABSTRACT METHODS - Must be implemented by each graph
    # ============================================================
    
    @abstractmethod
    def define_graph(self) -> Dict[str, Any]:
        """
        Define the graph structure.
        
        Returns a dict with:
        {
            "start": "start_node_name",
            "end": "end_node_name",
            "nodes": {
                "node_name": {
                    "handler": async function,
                    "description": str
                }
            },
            "edges": {
                "node_name": "next_node",           # fixed edge
                "node_name": ["next1", "next2"],    # conditional edge
                "node_name": {                      # routing dict
                    "condition1": "next1",
                    "condition2": "next2",
                    "default": "default_next"
                }
            }
        }
        """
        pass
    
    @abstractmethod
    def get_hitl_conditions(self) -> List[str]:
        """
        Return node names that require human-in-the-loop approval.
        These nodes trigger an interrupt BEFORE execution.
        """
        pass
    
    @abstractmethod
    def get_failure_conditions(self) -> List[str]:
        """
        Return node names where failures should create tickets.
        """
        pass
    
    @abstractmethod
    def get_node_timeout(self, node_name: str) -> Optional[int]:
        """
        Return timeout in seconds for a node.
        Returns None if no timeout.
        """
        pass
    
    # ============================================================
    # CHECKPOINTING - The Heart of Crash Recovery
    # ============================================================
    
    def _save_checkpoint(self):
        """
        Save the current state to durable storage.
        
        This is what enables crash recovery.
        The checkpoint proves which nodes completed and which work never started.
        """
        try:
            checkpoint_data = {
                "current_node": self.current_node,
                "state": self.state,
                "status": self.status.value,
                "iteration": self._iteration_count,
                "updated_at": datetime.now().isoformat()
            }
            
            db_save_checkpoint(
                graph_name=self.name,
                run_id=self.run_id,
                node_name=self.current_node or "start",
                state=checkpoint_data
            )
            
            print(f"[CHECKPOINT] {self.name} | {self.run_id} | Node: {self.current_node}")
            
        except Exception as e:
            print(f"[{self.name}] Checkpoint save failed: {e}")
    
    def _load_checkpoint(self, node_name: str) -> Optional[Dict]:
        """Load a specific checkpoint for a node."""
        try:
            checkpoint = db_get_checkpoint(
                graph_name=self.name,
                run_id=self.run_id,
                node_name=node_name
            )
            if checkpoint:
                return checkpoint.get("state")
            return None
        except Exception as e:
            print(f"[{self.name}] Checkpoint load failed: {e}")
            return None
    
    def _get_latest_checkpoint(self) -> Optional[Dict]:
        """Get the most recent checkpoint for this run."""
        try:
            checkpoint = db_get_latest_checkpoint(
                graph_name=self.name,
                run_id=self.run_id
            )
            if checkpoint:
                return checkpoint.get("state")
            return None
        except Exception as e:
            print(f"[{self.name}] Latest checkpoint load failed: {e}")
            return None
    
    # ============================================================
    # HITL - Human-in-the-Loop Gates
    # ============================================================
    
    def _create_hitl_task(self, node_name: str, state: Dict) -> int:
        """
        Create a HITL task in the web_platform.
        
        The graph pauses and waits for human action through the web_platform UI.
        
        The human can:
        - Approve: proceed with the action
        - Reject: stop the workflow
        - Modify: change state before proceeding
        """
        from web_platform.hitl import create_hitl_task as platform_create_hitl
        
        return platform_create_hitl(
            graph_name=self.name,
            run_id=self.run_id,
            node_name=node_name,
            state=state,
            priority=self._get_priority_for_node(node_name)
        )
    
    def _get_priority_for_node(self, node_name: str) -> str:
        """Determine priority based on node name."""
        if "urgent" in node_name or "emergency" in node_name:
            return "urgent"
        if "review" in node_name or "approval" in node_name:
            return "high"
        return "medium"
    
    # ============================================================
    # TICKETS - Unplanned Failure Recovery
    # ============================================================
    
    def _create_ticket(self, node_name: str, state: Dict, error: str) -> int:
        """
        Create a failure ticket.
        
        Different from HITL which is EXPECTED.
        
        Ticket lifecycle:
        1. OPEN: Failure detected, waiting for investigation
        2. INVESTIGATING: Admin is looking at it
        3. RESOLVED: Fixed, graph can resume
        
        A ticket is created when:
        - Tool call errors
        - Schema validation fails
        - Model returns something the graph can't act on
        - Timeout occurs on a critical node
        """
        from web_platform.tickets import create_ticket as platform_create_ticket
        
        return platform_create_ticket(
            graph_name=self.name,
            run_id=self.run_id,
            node_name=node_name,
            state=state,
            error_message=error,
            severity=self._get_severity_for_error(error)
        )
    
    def _get_severity_for_error(self, error: str) -> str:
        """Determine severity based on error message."""
        error_lower = error.lower()
        if any(kw in error_lower for kw in ["critical", "fatal", "data loss", "corrupt"]):
            return "critical"
        if any(kw in error_lower for kw in ["timeout", "failed", "invalid", "permission"]):
            return "high"
        if any(kw in error_lower for kw in ["warning", "unexpected", "retry"]):
            return "medium"
        return "low"
    
    # ============================================================
    # NODE EXECUTION - The Engine
    # ============================================================
    
    async def _execute_node(self, node_name: str, state: Dict) -> Dict:
        """Execute a node handler and return the result."""
        if node_name not in self.nodes:
            raise ValueError(f"Unknown node: {node_name}")
        
        handler = self.nodes[node_name]
        result = handler(state)
        # If handler is async, await it
        if asyncio.iscoroutine(result):
            return await result
        return result
    
    def _determine_next_node(self, current: str, result: Any) -> str:
        """
        Determine the next node based on routing logic.
        
        The routing function reads state and returns the next node name.
        It does NOT mutate state or ask an LLM.
        """
        if current not in self.edges:
            raise ValueError(f"No edges defined for node: {current}")
        
        edges = self.edges[current]
        
        # Case 1: Fixed edge - string
        if isinstance(edges, str):
            return edges
        
        # Case 2: Routing dict - result-based
        if isinstance(edges, dict):
            if isinstance(result, dict) and "next" in result:
                return result["next"]
            # Use default if provided
            return edges.get("default", list(edges.values())[0])
        
        # Case 3: List of possible next nodes
        if isinstance(edges, list):
            if len(edges) == 1:
                return edges[0]
            if isinstance(result, dict) and "next" in result:
                return result["next"]
            return edges[0]
        
        return edges
    
    # ============================================================
    # MAIN RUN LOOP - The Heart of the Graph
    # ============================================================
    
    async def run(self, initial_state: Dict[str, Any] = None, run_id: str = None):
        """
        Execute the state graph with checkpointing, HITL, and tickets.
        
        This implements patterns:
        1. Define nodes and edges
        2. Start at entry point
        3. For each node:
           a. Check if we should interrupt (HITL)
           b. Execute node
           c. Determine next node via routing
           d. Save checkpoint
        4. Handle failures with tickets
        
        The key insight: A checkpoint is saved after EVERY meaningful transition.
        """
        # Generate run_id if not provided
        self.run_id = run_id or f"{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.state = initial_state or {}
        self._iteration_count = 0
        
        # Define the graph structure
        graph_def = self.define_graph()
        
        # FIX: Extract ONLY the handler functions from the node definitions
        self.nodes = {
            name: node_def["handler"] 
            for name, node_def in graph_def["nodes"].items()
        }
        self.edges = graph_def["edges"]
        start_node = graph_def.get("start", "start")
        end_node = graph_def.get("end", "end")
        
        # Get HITL and failure conditions
        self.hitl_nodes = self.get_hitl_conditions()
        self.failure_nodes = self.get_failure_conditions()
        
        # Try to resume from checkpoint
        latest_checkpoint = self._get_latest_checkpoint()
        if latest_checkpoint:
            self.current_node = latest_checkpoint.get("current_node", start_node)
            self.state = latest_checkpoint.get("state", self.state)
            self.status = GraphStatus(latest_checkpoint.get("status", GraphStatus.RUNNING.value))
            self._iteration_count = latest_checkpoint.get("iteration", 0)
            print(f"[{self.name}] RESUME from checkpoint at node: {self.current_node}")
        else:
            self.current_node = start_node
            self.status = GraphStatus.RUNNING
            self._save_checkpoint()
        
        # If paused, wait for HITL resolution
        if self.status == GraphStatus.PAUSED:
            print(f"[{self.name}] PAUSED at {self.current_node}. Waiting for HITL resolution...")
            return {
                "status": "paused",
                "node": self.current_node,
                "state": self.state,
                "run_id": self.run_id
            }
        
        # If failed, exit
        if self.status == GraphStatus.FAILED:
            print(f"[{self.name}] FAILED at {self.current_node}. Check tickets.")
            return self.state
        
        # ============================================================
        # MAIN EXECUTION LOOP
        # ============================================================
        
        print(f"[{self.name}] Starting run {self.run_id}")
        
        while self.current_node != end_node and self._iteration_count < self._max_iterations:
            self._iteration_count += 1
            node = self.current_node
            
            # ============================================================
            # HITL CHECK - Pause before executing HITL nodes
            # ============================================================
            
            if node in self.hitl_nodes:
                self.status = GraphStatus.PAUSED
                task_id = self._create_hitl_task(node, self.state)
                self._save_checkpoint()
                print(f"[{self.name}] HITL PAUSE at {node}. Task: {task_id}")
                return {
                    "status": "paused",
                    "task_id": task_id,
                    "node": node,
                    "state": self.state,
                    "run_id": self.run_id
                }
            
            # ============================================================
            # EXECUTE NODE with timeout
            # ============================================================
            
            timeout = self.get_node_timeout(node)
            try:
                if timeout:
                    result = await asyncio.wait_for(
                        self._execute_node(node, self.state),
                        timeout=timeout
                    )
                else:
                    result = await self._execute_node(node, self.state)
            except asyncio.TimeoutError:
                error = f"Node '{node}' timed out after {timeout}s"
                if node in self.failure_nodes:
                    ticket_id = self._create_ticket(node, self.state, error)
                    self.status = GraphStatus.FAILED
                    self._save_checkpoint()
                    print(f"[{self.name}] TICKET created: {ticket_id}")
                    return {
                        "status": "failed",
                        "ticket_id": ticket_id,
                        "error": error,
                        "node": node,
                        "state": self.state,
                        "run_id": self.run_id
                    }
                raise TimeoutError(error)
            except Exception as e:
                error = str(e)
                if node in self.failure_nodes:
                    ticket_id = self._create_ticket(node, self.state, error)
                    self.status = GraphStatus.FAILED
                    self._save_checkpoint()
                    print(f"[{self.name}] TICKET created: {ticket_id}")
                    return {
                        "status": "failed",
                        "ticket_id": ticket_id,
                        "error": error,
                        "node": node,
                        "state": self.state,
                        "run_id": self.run_id
                    }
                raise
            
            # ============================================================
            # UPDATE STATE with result
            # ============================================================
            
            if isinstance(result, dict):
                self.state.update(result)
            else:
                self.state["result"] = result
            
            # ============================================================
            # DETERMINE NEXT NODE via routing
            # ============================================================
            
            next_node = self._determine_next_node(node, result)
            self.current_node = next_node
            
            # ============================================================
            # SAVE CHECKPOINT after each transition
            # ============================================================
            
            self._save_checkpoint()
            
            print(f"[{self.name}] {node} → {next_node}")
        
        # ============================================================
        # COMPLETED
        # ============================================================
        
        self.status = GraphStatus.COMPLETED
        self._save_checkpoint()
        print(f"[{self.name}] COMPLETED at {self.current_node}")
        
        return {
            "status": "completed",
            "state": self.state,
            "iterations": self._iteration_count,
            "run_id": self.run_id
        }
    
    # ============================================================
    # RESUME - For HITL and Ticket Recovery
    # ============================================================
    
    async def resume(self, decision: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Resume a paused graph with HITL decision.
        
        "Humans can correct the action—not just approve it."
        "update_state then invoke to replay from the pause point."
        
        The decision dict can contain:
        - approved: True/False
        - modified_state: changes to apply
        - notes: admin comments
        """
        # Load latest checkpoint
        checkpoint = self._get_latest_checkpoint()
        if not checkpoint:
            raise ValueError(f"No checkpoint found for run {self.run_id}")
        
        self.current_node = checkpoint.get("current_node")
        self.state = checkpoint.get("state", {})
        self.status = GraphStatus(checkpoint.get("status", GraphStatus.RUNNING.value))
        self._iteration_count = checkpoint.get("iteration", 0)
        
        # If paused, apply decision and resume
        if self.status == GraphStatus.PAUSED:
            if decision:
                # Apply the decision to state
                self.state["hitl_decision"] = decision
                
                # If the admin modified state, apply those changes
                if decision.get("modified_state"):
                    self.state.update(decision["modified_state"])
                
                # If approved, continue
                if decision.get("approved", True):
                    self.status = GraphStatus.RUNNING
                    self._save_checkpoint()
                    
                    # Re-run from current node (which is the HITL node)
                    # The node will see the decision and proceed
                    return await self.run(self.state, self.run_id)
                else:
                    # Rejected - end the workflow
                    self.status = GraphStatus.COMPLETED
                    self.state["final_status"] = "rejected"
                    self._save_checkpoint()
                    return {
                        "status": "rejected",
                        "state": self.state,
                        "run_id": self.run_id
                    }
            
            # No decision - still paused
            return {
                "status": "paused",
                "node": self.current_node,
                "state": self.state,
                "run_id": self.run_id
            }
        
        return self.state