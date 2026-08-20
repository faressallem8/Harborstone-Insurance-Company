# platform/app.py
"""Harborstone Insurance Platform - Main Application."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Import from platform modules
from platform.database import (
    get_connection,
    # HITL
    get_pending_hitl_tasks,
    get_hitl_task,
    resolve_hitl_task,
    create_hitl_task,
    # Tickets
    get_open_tickets,
    get_ticket,
    resolve_ticket,
    create_ticket,
    # Tools
    get_all_tools,
    get_tools_for_agent,
    register_tool,
    update_tool,
    delete_tool,
    # Documents
    get_all_documents,
    add_document,
    update_document_status,
    delete_document,
    # Checkpoints
    save_checkpoint,
    get_checkpoint,
    get_latest_checkpoint,
)

from platform.models import (
    ChatRequest,
    ChatResponse,
    ToolToggle,
    RAGDocument,
    ToolRegistryCreate,
    ToolRegistryUpdate,
    HITLTaskCreate,
    HITLResolution,
    TicketCreate,
    TicketResolution,
    APIResponse,
    AgentInfo,
    AgentListResponse,
)

load_dotenv(project_root / ".env")

app = FastAPI(title="Harborstone Insurance Platform")

# Mount static files
app.mount("/static", StaticFiles(directory="platform/static"), name="static")

# Create Jinja2 environment
jinja_env = Environment(
    loader=FileSystemLoader("platform/templates"),
    autoescape=select_autoescape(['html', 'xml']),
    cache_size=0,
    auto_reload=True
)

def render_template(template_name: str, context: dict) -> str:
    """Render a template with the given context."""
    template = jinja_env.get_template(template_name)
    return template.render(**context)


# ============================================================
# USER ROUTES
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Home page - user chat interface."""
    html = render_template("index.html", {"request": request})
    return HTMLResponse(content=html)


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard."""
    html = render_template("admin.html", {"request": request})
    return HTMLResponse(content=html)


@app.get("/api/agents")
async def list_agents():
    """List all available agents with their tools."""
    agents = [
        {
            "id": "appeal",
            "name": "Appeal Agent",
            "description": "Handle claim appeals with HITL",
            "type": "state_graph"
        },
        {
            "id": "renewal",
            "name": "Renewal Agent",
            "description": "Policy renewal assessments with RAG",
            "type": "state_graph"
        },
        {
            "id": "fraud",
            "name": "Fraud Agent",
            "description": "Fraud investigation with LATS",
            "type": "state_graph"
        },
        {
            "id": "memory_rag",
            "name": "Memory & RAG Agent",
            "description": "Front-desk triage and clinical policy",
            "type": "rag"
        },
        {
            "id": "planning",
            "name": "Planning Agent",
            "description": "Decomposition and planning",
            "type": "planning"
        },
    ]

    # Get tools for each agent from database
    for agent in agents:
        try:
            tools = get_tools_for_agent(agent["name"], enabled_only=True)
            agent["tools"] = [t["tool_name"] for t in tools]
        except:
            agent["tools"] = []

    return {"agents": agents, "total": len(agents)}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Chat endpoint - routes to the appropriate agent.
    Person B will replace this with actual agent integration.
    """
    # TODO: Person B - Integrate with real agents
    # This is a placeholder that uses the database to check if agent exists

    # Check if agent has tools enabled
    tools = get_tools_for_agent(request.agent, enabled_only=True)

    if not tools:
        return ChatResponse(
            reply=f"Agent '{request.agent}' has no tools enabled. Please contact admin.",
            agent=request.agent
        )

    # Mock reply - Person B will replace this
    mock_replies = {
        "appeal": f"🔍 I'll help you appeal that claim. Your message: '{request.message}'\n\nAvailable tools: {[t['tool_name'] for t in tools]}",
        "renewal": f"📋 I'm checking the policy renewal. Your message: '{request.message}'\n\nAvailable tools: {[t['tool_name'] for t in tools]}",
        "fraud": f"🕵️ Investigating fraud claim. Your message: '{request.message}'\n\nAvailable tools: {[t['tool_name'] for t in tools]}",
        "memory_rag": f"📚 I'll search through our documents. Your message: '{request.message}'",
        "planning": f"📊 I'll plan this for you. Your message: '{request.message}'",
    }

    reply = mock_replies.get(request.agent, f"Hello! How can I help with '{request.message}'?")

    return ChatResponse(reply=reply, agent=request.agent)


# ============================================================
# TOOLS MANAGEMENT ROUTES
# ============================================================

@app.get("/api/admin/tools")
async def get_tools():
    """Get all tool registry entries."""
    try:
        tools = get_all_tools()
        return APIResponse(status="success", data=tools)
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.get("/api/admin/tools/agent/{agent_name}")
async def get_agent_tools(agent_name: str, enabled_only: bool = True):
    """Get tools for a specific agent."""
    try:
        tools = get_tools_for_agent(agent_name, enabled_only)
        return APIResponse(status="success", data={
            "agent": agent_name,
            "tools": tools,
            "total": len(tools)
        })
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.post("/api/admin/tools")
async def register_tool_endpoint(data: ToolRegistryCreate):
    """Register a tool for an agent."""
    try:
        result = register_tool(data.tool_name, data.agent_name, data.enabled)
        return APIResponse(status="success", data=result)
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.put("/api/admin/tools/{tool_id}")
async def update_tool_endpoint(tool_id: int, data: ToolRegistryUpdate):
    """Update a tool's status."""
    try:
        result = update_tool(tool_id, data.enabled)
        return APIResponse(status="success", data=result)
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.delete("/api/admin/tools/{tool_id}")
async def delete_tool_endpoint(tool_id: int):
    """Delete a tool registry entry."""
    try:
        success = delete_tool(tool_id)
        if success:
            return APIResponse(status="success", data={"deleted": True})
        return APIResponse(status="error", error="Tool not found")
    except Exception as e:
        return APIResponse(status="error", error=str(e))


# ============================================================
# RAG DOCUMENTS ROUTES
# ============================================================

@app.get("/api/admin/documents")
async def get_documents(active_only: bool = True):
    """Get all RAG documents."""
    try:
        docs = get_all_documents(active_only)
        return APIResponse(status="success", data=docs)
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.post("/api/admin/documents")
async def add_document_endpoint(data: RAGDocument):
    """Add a new RAG document."""
    try:
        result = add_document(data.name, data.content, data.source, data.active)
        return APIResponse(status="success", data=result)
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.put("/api/admin/documents/{doc_id}")
async def update_document_status_endpoint(doc_id: int, request: Request):
    """
    Update a document's status.
    Accepts either query parameter ?active=false or JSON body {"active": false}
    """
    try:
        # Try to get from query parameter first
        query_params = dict(request.query_params)
        if "active" in query_params:
            active = query_params["active"].lower() == "true"
        else:
            # Try to get from JSON body
            data = await request.json()
            active = data.get("active")
            if active is None:
                return APIResponse(status="error", error="active field required")

        result = update_document_status(doc_id, active)
        return APIResponse(status="success", data=result)
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.delete("/api/admin/documents/{doc_id}")
async def delete_document_endpoint(doc_id: int):
    """Delete a document (soft delete)."""
    try:
        success = delete_document(doc_id)
        if success:
            return APIResponse(status="success", data={"deleted": True})
        return APIResponse(status="error", error="Document not found")
    except Exception as e:
        return APIResponse(status="error", error=str(e))


# ============================================================
# HITL ROUTES
# ============================================================

@app.get("/api/admin/hitl")
async def get_hitl_tasks():
    """Get all pending HITL tasks."""
    try:
        tasks = get_pending_hitl_tasks()
        return APIResponse(status="success", data={"tasks": tasks, "total": len(tasks)})
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.get("/api/admin/hitl/{task_id}")
async def get_hitl_task_detail(task_id: int):
    """Get a specific HITL task."""
    try:
        task = get_hitl_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return APIResponse(status="success", data=task)
    except HTTPException:
        raise
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.post("/api/admin/hitl/{task_id}/resolve")
async def resolve_hitl_endpoint(task_id: int, resolution: HITLResolution):
    """Resolve a HITL task."""
    try:
        result = resolve_hitl_task(
            task_id,
            resolution.decision,
            resolution.status,
            resolution.notes  # ← Pass notes to database
        )
        return APIResponse(status="success", data=result)
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.post("/api/hitl")  # Called by state graphs
async def create_hitl_task_endpoint(data: HITLTaskCreate):
    """Create a new HITL task (called from state graphs)."""
    try:
        result = create_hitl_task(
            data.graph_name,
            data.run_id,
            data.node_name,
            data.state,
            data.assigned_to,
            data.priority
        )
        return APIResponse(status="success", data=result)
    except Exception as e:
        return APIResponse(status="error", error=str(e))


# ============================================================
# TICKET ROUTES
# ============================================================

@app.get("/api/admin/tickets")
async def get_tickets():
    """Get all open tickets."""
    try:
        tickets = get_open_tickets()
        return APIResponse(status="success", data={"tickets": tickets, "total": len(tickets)})
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.get("/api/admin/tickets/{ticket_id}")
async def get_ticket_detail(ticket_id: int):
    """Get a specific ticket."""
    try:
        ticket = get_ticket(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        return APIResponse(status="success", data=ticket)
    except HTTPException:
        raise
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.post("/api/admin/tickets/{ticket_id}/resolve")
async def resolve_ticket_endpoint(ticket_id: int, resolution: TicketResolution):
    """Resolve a ticket."""
    try:
        result = resolve_ticket(ticket_id, resolution.status, resolution.resolution_notes)
        return APIResponse(status="success", data=result)
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.post("/api/tickets")  # Called by state graphs
async def create_ticket_endpoint(data: TicketCreate):
    """Create a new ticket (called from state graphs)."""
    try:
        result = create_ticket(
            data.graph_name,
            data.run_id,
            data.node_name,
            data.state,
            data.error_message,
            data.error_type,
            data.assigned_to,
            data.severity
        )
        return APIResponse(status="success", data=result)
    except Exception as e:
        return APIResponse(status="error", error=str(e))


# ============================================================
# CHECKPOINT ROUTES
# ============================================================

@app.post("/api/checkpoints")
async def save_checkpoint_endpoint(request: Request):
    """Save a checkpoint (called from state graphs)."""
    try:
        data = await request.json()
        result = save_checkpoint(
            data.get("graph_name"),
            data.get("run_id"),
            data.get("node_name"),
            data.get("state", {})
        )
        return APIResponse(status="success", data=result)
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.get("/api/checkpoints/{graph_name}/{run_id}/latest")
async def get_latest_checkpoint_endpoint(graph_name: str, run_id: str):
    """Get the latest checkpoint for a run."""
    try:
        checkpoint = get_latest_checkpoint(graph_name, run_id)
        if not checkpoint:
            raise HTTPException(status_code=404, detail="No checkpoint found")
        return APIResponse(status="success", data=checkpoint)
    except HTTPException:
        raise
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.get("/api/checkpoints/{graph_name}/{run_id}/{node_name}")
async def get_checkpoint_endpoint(graph_name: str, run_id: str, node_name: str):
    """Get a specific checkpoint."""
    try:
        checkpoint = get_checkpoint(graph_name, run_id, node_name)
        if not checkpoint:
            raise HTTPException(status_code=404, detail="Checkpoint not found")
        return APIResponse(status="success", data=checkpoint)
    except HTTPException:
        raise
    except Exception as e:
        return APIResponse(status="error", error=str(e))


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)