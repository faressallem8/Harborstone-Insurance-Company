"""Pydantic models for the web_platform API."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


# ============================================================
# Basic Models
# ============================================================

class ChatRequest(BaseModel):
    """Request from a user to chat with an agent"""
    agent: str = Field(..., description="Agent name to chat with")
    message: str = Field(..., description="User's message")
    session_id: Optional[str] = Field(None, description="Optional session ID for stateful chat")


class ChatResponse(BaseModel):
    """Response from an agent"""
    reply: str = Field(..., description="Agent's reply")
    agent: str = Field(..., description="Agent that replied")
    session_id: Optional[str] = Field(None, description="Session ID for stateful chat")


class ToolToggle(BaseModel):
    """Toggle a tool on/off for a specific agent"""
    tool_name: str = Field(..., description="Name of the tool")
    agent_name: str = Field(..., description="Name of the agent")
    enabled: bool = Field(..., description="Enable or disable the tool")


# ============================================================
# Enums
# ============================================================

class HITLStatus(str, Enum):
    """Status of a Human-in-the-Loop task"""
    PENDING = "pending"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class TicketStatus(str, Enum):
    """Status of a failure ticket"""
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"


class Priority(str, Enum):
    """Priority levels for HITL tasks"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Severity(str, Enum):
    """Severity levels for tickets (aligned with SQL CHECK constraint)"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================
# HITL Task Models
# ============================================================

class HITLTask(BaseModel):
    """Human-in-the-Loop task model"""
    id: Optional[int] = None
    graph_name: str = Field(..., description="Graph name that paused")
    run_id: str = Field(..., description="Run ID of the graph")
    node_name: str = Field(..., description="Node that paused")
    state: Dict[str, Any] = Field(..., description="Full graph state")
    decision: Optional[Dict[str, Any]] = Field(None, description="Admin's decision")
    status: HITLStatus = Field(HITLStatus.PENDING, description="Task status")
    assigned_to: Optional[str] = Field(None, description="Assigned admin username")
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = Field(None, description="Resolution notes from admin")
    priority: Priority = Field(Priority.MEDIUM, description="Task priority")


class HITLTaskCreate(BaseModel):
    """Create a new HITL task"""
    graph_name: str = Field(..., description="Graph name that paused")
    run_id: str = Field(..., description="Run ID of the graph")
    node_name: str = Field(..., description="Node that paused")
    state: Dict[str, Any] = Field(..., description="Full graph state")
    assigned_to: Optional[str] = Field(None, description="Assigned admin username")
    priority: Priority = Field(Priority.MEDIUM, description="Task priority")


class HITLResolution(BaseModel):
    """Admin's resolution for a HITL task"""
    decision: Dict[str, Any] = Field(..., description="Admin's decision data")
    status: HITLStatus = Field(HITLStatus.RESOLVED, description="Resolution status")
    notes: Optional[str] = Field(None, description="Resolution notes (stored in resolution_notes)")


# ============================================================
# Ticket Models
# ============================================================

class Ticket(BaseModel):
    """Failure ticket model"""
    id: Optional[int] = None
    graph_name: str = Field(..., description="Graph name that failed")
    run_id: str = Field(..., description="Run ID of the graph")
    node_name: Optional[str] = Field(None, description="Node that failed")
    state: Optional[Dict[str, Any]] = Field(None, description="Graph state at failure")
    error_message: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Type of error")
    status: TicketStatus = Field(TicketStatus.OPEN, description="Ticket status")
    assigned_to: Optional[str] = Field(None, description="Assigned admin username")
    resolution_notes: Optional[str] = Field(None, description="Resolution notes")
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    severity: Severity = Field(Severity.MEDIUM, description="Ticket severity")


class TicketCreate(BaseModel):
    """Create a new ticket"""
    graph_name: str = Field(..., description="Graph name that failed")
    run_id: str = Field(..., description="Run ID of the graph")
    node_name: Optional[str] = Field(None, description="Node that failed")
    state: Optional[Dict[str, Any]] = Field(None, description="Graph state at failure")
    error_message: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Type of error")
    assigned_to: Optional[str] = Field(None, description="Assigned admin username")
    severity: Severity = Field(Severity.MEDIUM, description="Ticket severity")


class TicketResolution(BaseModel):
    """Admin's resolution for a ticket"""
    status: TicketStatus = Field(TicketStatus.RESOLVED, description="Resolution status")
    resolution_notes: str = Field(..., description="Resolution notes")


# ============================================================
# Checkpoint Models
# ============================================================

class GraphCheckpoint(BaseModel):
    """Graph checkpoint for crash recovery"""
    id: Optional[int] = None
    graph_name: str = Field(..., description="Graph name")
    run_id: str = Field(..., description="Run ID of the graph")
    node_name: str = Field(..., description="Current node")
    state: Dict[str, Any] = Field(..., description="Full graph state")
    created_at: Optional[datetime] = None


class GraphCheckpointCreate(BaseModel):
    """Create a new checkpoint"""
    graph_name: str = Field(..., description="Graph name")
    run_id: str = Field(..., description="Run ID of the graph")
    node_name: str = Field(..., description="Current node")
    state: Dict[str, Any] = Field(..., description="Full graph state")


# ============================================================
# Tool Registry Models
# ============================================================

class ToolRegistry(BaseModel):
    """Tool registry entry"""
    id: Optional[int] = None
    tool_name: str = Field(..., description="Name of the tool")
    agent_name: str = Field(..., description="Name of the agent")
    enabled: bool = Field(True, description="Whether the tool is enabled")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ToolRegistryCreate(BaseModel):
    """Create a new tool registry entry"""
    tool_name: str = Field(..., description="Name of the tool")
    agent_name: str = Field(..., description="Name of the agent")
    enabled: bool = Field(True, description="Whether the tool is enabled")


class ToolRegistryUpdate(BaseModel):
    """Update a tool registry entry"""
    enabled: bool = Field(..., description="Enable or disable the tool")


# ============================================================
# RAG Document Models
# ============================================================

class RAGDocument(BaseModel):
    """RAG document model"""
    id: Optional[int] = None
    name: str = Field(..., description="Document name")
    content: str = Field(..., description="Document content")
    source: Optional[str] = Field(None, description="Document source")
    active: bool = Field(True, description="Whether the document is active")
    added_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RAGDocumentCreate(BaseModel):
    """Create a new RAG document"""
    name: str = Field(..., description="Document name")
    content: str = Field(..., description="Document content")
    source: Optional[str] = Field(None, description="Document source")
    active: bool = Field(True, description="Whether the document is active")


class RAGDocumentUpdate(BaseModel):
    """Update a RAG document"""
    active: bool = Field(..., description="Activate or deactivate the document")


# ============================================================
# Agent Models (for UI)
# ============================================================

class AgentInfo(BaseModel):
    """Agent information for the UI"""
    id: str = Field(..., description="Unique agent ID")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Agent description")
    type: str = Field(..., description="Agent type: state_graph, rag, planning")
    tools: List[str] = Field(default_factory=list, description="Available tools")


class AgentListResponse(BaseModel):
    """Response for listing agents"""
    agents: List[AgentInfo] = Field(..., description="List of agents")
    total: int = Field(..., description="Total number of agents")


# ============================================================
# API Response Wrappers
# ============================================================

class APIResponse(BaseModel):
    """Standard API response wrapper"""
    status: str = Field(..., description="success or error")
    data: Optional[Any] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if status is error")


class PaginatedResponse(BaseModel):
    """Paginated API response"""
    items: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(1, description="Current page number")
    per_page: int = Field(20, description="Items per page")
    pages: int = Field(1, description="Total number of pages")