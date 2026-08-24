"""Harborstone Insurance Platform - Main Application."""

import sys
import re
import subprocess
import atexit
import signal
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Import from web_platform modules
from web_platform.database import (
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

from web_platform.models import (
    ChatRequest,
    ChatResponse,
    RAGDocument,
    ToolRegistryCreate,
    ToolRegistryUpdate,
    HITLTaskCreate,
    HITLResolution,
    TicketCreate,
    TicketResolution,
    APIResponse,
)

# Import State Graphs
from state_graph import AppealGraph, RenewalGraph, FraudGraph
from mcp_server.server import tool_registry
load_dotenv(project_root / ".env")

app = FastAPI(title="Harborstone Insurance Platform")

mcp_server_process = None

def start_mcp_server():
    """Start the MCP server as a background subprocess."""
    global mcp_server_process
    if mcp_server_process is not None and mcp_server_process.poll() is None:
        print("[MCP] Server already running.")
        return
    cmd = [sys.executable, "-m", "mcp_server.server"]
    try:
        mcp_server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        print(f"[MCP] Server started with PID {mcp_server_process.pid}")
    except Exception as e:
        print(f"[MCP] Failed to start server: {e}")

def stop_mcp_server():
    """Terminate the MCP server subprocess."""
    global mcp_server_process
    if mcp_server_process is not None and mcp_server_process.poll() is None:
        try:
            mcp_server_process.terminate()
            mcp_server_process.wait(timeout=5)
            print("[MCP] Server stopped.")
        except Exception as e:
            print(f"[MCP] Error stopping server: {e}")

# Ensure the server is stopped when the Python process exits
atexit.register(stop_mcp_server)

@app.on_event("startup")
async def startup_event():
    """Initialize the tool registry and start the MCP server."""
    # Initialize tool registry
    await tool_registry.initialize()
    print("[PLATFORM] Tool registry initialized.")
    for agent, tools in tool_registry.tools_cache.items():
        print(f"  - {agent}: {list(tools.keys())}")
        enabled = [name for name, enabled in tools.items() if enabled]
        if enabled:
            print(f"  - {agent}: {', '.join(enabled)}")
    # Start MCP server as background process
    start_mcp_server()



# Mount static files
app.mount("/static", StaticFiles(directory="web_platform/static"), name="static")

# Create Jinja2 environment
jinja_env = Environment(
    loader=FileSystemLoader("web_platform/templates"),
    autoescape=select_autoescape(['html', 'xml']),
    cache_size=0,
    auto_reload=True
)


def render_template(template_name: str, context: dict) -> str:
    """Render a template with the given context."""
    template = jinja_env.get_template(template_name)
    return template.render(**context)


# ============================================================
# GRAPH EXECUTION HELPER
# ============================================================

async def execute_graph(agent: str, message: str, session_id: str = None) -> Dict[str, Any]:
    """
    Execute a state graph based on the agent type.

    This replaces the mock chat with real graph execution.

    Args:
        agent: The agent ID (appeal, renewal, fraud)
        message: The user's message
        session_id: Optional session ID for resuming

    Returns:
        Dict with reply and session_id
    """
    # Try to extract IDs from the message
    claim_match = re.search(r"claim\s*#?\s*(\d+)", message, re.IGNORECASE)
    policy_match = re.search(r"policy\s*#?\s*(\d+)", message, re.IGNORECASE)

    # Default IDs for demo
    claim_id = int(claim_match.group(1)) if claim_match else 11
    policy_id = int(policy_match.group(1)) if policy_match else 1

    # Try to resume an existing run if session_id provided
    if session_id:
        # Check if there's a checkpoint for this session
        checkpoint = get_latest_checkpoint(
            graph_name=f"{agent}_graph",
            run_id=session_id
        )

        if checkpoint:
            # Resume the graph
            state = checkpoint.get("state", {})
            status = state.get("status", "")

            if status == "paused":
                # This is a HITL pause - we need the admin to resolve it
                # The user can't resume HITL tasks directly
                return {
                    "reply": f"This session is paused waiting for admin review. Task ID: {state.get('task_id', 'Unknown')}",
                    "session_id": session_id,
                    "paused": True
                }
            elif status == "failed":
                return {
                    "reply": f"This session failed. Ticket ID: {state.get('ticket_id', 'Unknown')}. Please contact admin.",
                    "session_id": session_id,
                    "failed": True
                }

    # Execute the appropriate graph
    try:
        if agent == "appeal":
            graph = AppealGraph(agent_name="appeal")
            result = await graph.run(
                initial_state={
                    "claim_id": claim_id,
                    "user_message": message
                },
                run_id=session_id or f"appeal_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )

            return _format_graph_result(result, "appeal")

        elif agent == "renewal":
            graph = RenewalGraph(agent_name="renewal")
            result = await graph.run(
                initial_state={
                    "policy_id": policy_id,
                    "user_message": message
                },
                run_id=session_id or f"renewal_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )

            return _format_graph_result(result, "renewal")

        elif agent == "fraud":
            graph = FraudGraph(agent_name="fraud")
            result = await graph.run(
                initial_state={
                    "claim_id": claim_id,
                    "user_message": message
                },
                run_id=session_id or f"fraud_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )

            return _format_graph_result(result, "fraud")

        else:
            return {
                "reply": f"Unknown agent: {agent}",
                "session_id": None
            }

    except Exception as e:
        return {
            "reply": f"Error executing graph: {str(e)}",
            "session_id": None,
            "error": str(e)
        }


def _format_graph_result(result: Dict[str, Any], agent_type: str) -> Dict[str, Any]:
    """
    Format the graph result for the chat response.

    Args:
        result: The result from graph.run()
        agent_type: The type of agent

    Returns:
        Dict with reply and session_id
    """
    status = result.get("status")
    run_id = result.get("run_id")
    state = result.get("state", {})

    # HITL PAUSED
    if status == "paused":
        task_id = result.get("task_id")
        node = result.get("node")

        messages = {
            "appeal": f"**Appeal Paused - Waiting for Documents**\n\n"
                      f"The appeal for claim #{state.get('claim_id', 'Unknown')} is waiting for you to upload documents.\n\n"
                      f"**Documents Needed:**\n" + "\n".join(f"- {doc}" for doc in state.get('documents_needed', [])) +
                      f"\n\n**Task ID:** {task_id}\n"
                      f"**Node:** {node}\n"
                      f"**Session:** {run_id}",

            "renewal": f"**Renewal Paused - Waiting for Underwriter Review**\n\n"
                       f"The renewal for policy #{state.get('policy_id', 'Unknown')} needs underwriter review.\n\n"
                       f"**Risk Score:** {state.get('risk_score', 'N/A')}\n"
                       f"**Risk Level:** {state.get('risk_level', 'N/A')}\n"
                       f"**Risk Factors:** {', '.join(state.get('risk_factors', ['None']))}\n\n"
                       f"**Task ID:** {task_id}\n"
                       f"**Node:** {node}\n"
                       f"**Session:** {run_id}",

            "fraud": f"**Fraud Investigation Paused - Waiting for Review**\n\n"
                     f"The fraud investigation for claim #{state.get('claim_id', 'Unknown')} needs review.\n\n"
                     f"**Review Level:** {state.get('review_level', 'Unknown')}\n"
                     f"**Fraud Risk:** {state.get('fraud_risk', 'Unknown')}\n"
                     f"**Investigation Score:** {state.get('investigation_score', 'N/A')}\n\n"
                     f"**Task ID:** {task_id}\n"
                     f"**Node:** {node}\n"
                     f"**Session:** {run_id}"
        }

        return {
            "reply": messages.get(agent_type, f"Graph paused at {node}"),
            "session_id": run_id,
            "paused": True,
            "task_id": task_id
        }

    # COMPLETED
    elif status == "completed":
        messages = {
            "appeal": f"**Appeal Completed!**\n\n"
                      f"**Claim ID:** {state.get('claim_id', 'Unknown')}\n"
                      f"**Appeal Status:** {state.get('appeal_status', 'Unknown')}\n"
                      f"**Strategy:** {state.get('strategy', 'Unknown')}\n"
                      f"**Steps:** {', '.join(state.get('appeal_steps', []))}\n\n"
                      f"**Session:** {run_id}",

            "renewal": f"**Renewal Completed!**\n\n"
                       f"**Policy ID:** {state.get('policy_id', 'Unknown')}\n"
                       f"**Policy Number:** {state.get('policy_number', 'Unknown')}\n"
                       f"**Renewal Status:** {state.get('renewal_status', 'Unknown')}\n"
                       f"**Risk Score:** {state.get('risk_score', 'N/A')}\n"
                       f"**Steps:** {', '.join(state.get('renewal_steps', []))}\n\n"
                       f"**Session:** {run_id}",

            "fraud": f"**Fraud Investigation Completed!**\n\n"
                     f"**Claim ID:** {state.get('claim_id', 'Unknown')}\n"
                     f"**Fraud Status:** {state.get('fraud_status', 'Unknown')}\n"
                     f"**Fraud Risk:** {state.get('fraud_risk', 'Unknown')}\n"
                     f"**Steps:** {', '.join(state.get('fraud_steps', []))}\n\n"
                     f"**Session:** {run_id}"
        }

        return {
            "reply": messages.get(agent_type, f"Graph completed"),
            "session_id": run_id,
            "completed": True
        }

    # FAILED
    elif status == "failed":
        ticket_id = result.get("ticket_id")
        error = result.get("error", "Unknown error")

        return {
            "reply": f"**Graph Failed**\n\n"
                     f"**Error:** {error}\n"
                     f"**Ticket ID:** {ticket_id}\n"
                     f"**Node:** {result.get('node', 'Unknown')}\n\n"
                     f"An admin has been notified and will investigate.\n"
                     f"**Session:** {run_id}",
            "session_id": run_id,
            "failed": True,
            "ticket_id": ticket_id
        }

    # REJECTED (HITL rejection)
    elif status == "rejected":
        return {
            "reply": f"**Request Rejected**\n\n"
                     f"Your request was rejected by the administrator.\n"
                     f"**Reason:** {state.get('final_status', 'No reason provided')}\n"
                     f"**Session:** {run_id}",
            "session_id": run_id,
            "rejected": True
        }

    # Default
    else:
        return {
            "reply": f"Graph result: {result}",
            "session_id": run_id
        }


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
            "description": "Handle claim appeals with HITL (ToT + Constrained ReAct)",
            "type": "state_graph"
        },
        {
            "id": "renewal",
            "name": "Renewal Agent",
            "description": "Policy renewal assessments with RAG (RAG + Decomposition)",
            "type": "state_graph"
        },
        {
            "id": "fraud",
            "name": "Fraud Agent",
            "description": "Fraud investigation with LATS (LATS + Constrained ReAct)",
            "type": "state_graph"
        }
    ]

    # Get tools for each agent from database
    for agent in agents:
        try:
            print(f"[DEBUG] Looking for tools for agent '{agent['id']}'")
            tools = get_tools_for_agent(agent["id"], enabled_only=True)
            print(f"[DEBUG] Found tools: {tools}")
            agent["tools"] = [t["tool_name"] for t in tools]
        except:
            agent["tools"] = []

    return {"agents": agents, "total": len(agents)}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Chat endpoint - routes to the appropriate agent.

    Now uses REAL state graph execution instead of mocks.
    """
    # First, check if agent has tools enabled (for MCP tools)
    tools = get_tools_for_agent(request.agent, enabled_only=True)


    tools_check = get_tools_for_agent(request.agent, enabled_only=True)

    # Only check tools for state_graph agents that need MCP tools
    if request.agent in ["appeal", "renewal", "fraud"] and not tools_check:
        return ChatResponse(
            reply=f"Agent '{request.agent}' has no MCP tools enabled. "
                  f"Please contact admin to enable tools.\n\n"
                  f"Try: 'I want to appeal claim 11' or 'Check policy 1'",
            agent=request.agent
        )

    # Execute the state graph
    result = await execute_graph(
        agent=request.agent,
        message=request.message,
        session_id=request.session_id
    )

    return ChatResponse(
        reply=result.get("reply", "No response from agent"),
        agent=request.agent,
        session_id=result.get("session_id")
    )


# ============================================================
# HITL RESUMPTION (For admin use)
# ============================================================

@app.post("/api/admin/hitl/{task_id}/resume")
async def resume_hitl_task(task_id: int, resolution: HITLResolution):
    """
    Resume a graph after HITL resolution.
    This is called by the admin after resolving a HITL task.
    """
    try:
        # Get the task
        task = get_hitl_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        graph_name = task.get("graph_name")
        run_id = task.get("run_id")

        # Determine which graph to resume
        graph_map = {
            "appeal_graph": AppealGraph,
            "renewal_graph": RenewalGraph,
            "fraud_graph": FraudGraph,
        }

        graph_class = graph_map.get(graph_name)
        if not graph_class:
            return APIResponse(
                status="error",
                error=f"Unknown graph: {graph_name}"
            )

        # Create graph instance and resume
        agent_name = graph_name.replace("_graph", "")
        graph = graph_class(agent_name=agent_name)

        # Set the run_id
        graph.run_id = run_id

        # Resume with the admin's decision
        result = await graph.resume(
            decision=resolution.decision
        )

        return APIResponse(
            status="success",
            data={
                "graph": graph_name,
                "run_id": run_id,
                "result": result
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        return APIResponse(status="error", error=str(e))


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
    """
    Resolve a HITL task AND resume the graph.
    This is the complete fix for HITL continuation.
    """
    try:
        # 1. Get the task
        task = get_hitl_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        graph_name = task.get("graph_name")
        run_id = task.get("run_id")

        # 2. Resolve the HITL task in database
        result = resolve_hitl_task(
            task_id,
            resolution.decision,
            resolution.status,
            resolution.notes
        )

        # 3. Determine which graph to resume
        graph_map = {
            "appeal_graph": AppealGraph,
            "renewal_graph": RenewalGraph,
            "fraud_graph": FraudGraph,
        }

        graph_class = graph_map.get(graph_name)
        if not graph_class:
            return APIResponse(
                status="error",
                error=f"Unknown graph: {graph_name}"
            )

        # 4. Resume the graph
        agent_name = graph_name.replace("_graph", "")
        graph = graph_class(agent_name=agent_name)
        graph.run_id = run_id

        resume_result = await graph.resume(
            decision=resolution.decision
        )

        return APIResponse(
            status="success",
            data={
                "task": result,
                "graph": graph_name,
                "run_id": run_id,
                "resume_result": resume_result
            }
        )

    except HTTPException:
        raise
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
    """Resolve a ticket. Note: this only updates the ticket record — it does
    NOT resume the underlying graph run. Call /resume for that."""
    try:
        result = resolve_ticket(ticket_id, resolution.status, resolution.resolution_notes)
        return APIResponse(status="success", data=result)
    except Exception as e:
        return APIResponse(status="error", error=str(e))


@app.post("/api/admin/tickets/{ticket_id}/resume")
async def resume_ticket_task(ticket_id: int, resolution: TicketResolution):
    """
    Resolve a ticket AND resume the graph run from its last checkpoint.
    This is the ticket-recovery equivalent of /api/admin/hitl/{task_id}/resume.
    """
    try:
        ticket = get_ticket(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        graph_name = ticket.get("graph_name")
        run_id = ticket.get("run_id")

        graph_map = {
            "appeal_graph": AppealGraph,
            "renewal_graph": RenewalGraph,
            "fraud_graph": FraudGraph,
        }

        graph_class = graph_map.get(graph_name)
        if not graph_class:
            return APIResponse(status="error", error=f"Unknown graph: {graph_name}")

        # Mark the ticket resolved first
        resolve_ticket(ticket_id, resolution.status, resolution.resolution_notes)

        # Then resume the graph from its checkpoint
        agent_name = graph_name.replace("_graph", "")
        graph = graph_class(agent_name=agent_name)
        graph.run_id = run_id

        result = await graph.resume(decision={"notes": resolution.resolution_notes})

        return APIResponse(
            status="success",
            data={
                "graph": graph_name,
                "run_id": run_id,
                "ticket_id": ticket_id,
                "result": result
            }
        )

    except HTTPException:
        raise
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