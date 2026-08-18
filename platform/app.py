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

from platform.database import get_connection
from platform.hitl import (
    get_hitl_task, list_pending_hitl, resolve_hitl_task
)
from platform.tickets import (
    get_ticket, list_open_tickets, resolve_ticket
)
from platform.models import ChatRequest, ChatResponse, ToolToggle, RAGDocument

load_dotenv(project_root / ".env")

app = FastAPI(title="Harborstone Insurance Platform")

app.mount("/static", StaticFiles(directory="platform/static"), name="static")

# Create Jinja2 environment with caching disabled
jinja_env = Environment(
    loader=FileSystemLoader("platform/templates"),
    autoescape=select_autoescape(['html', 'xml']),
    cache_size=0,          # Disable cache to fix unhashable dict issue
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
    html = render_template("index.html", {"request": request})
    return HTMLResponse(content=html)

@app.post("/api/chat")
async def chat(request: ChatRequest):
    # MOCK reply - Person B will replace this
    mock_replies = {
        "appeal": f"I'll help you appeal that claim. Processing: '{request.message}'",
        "renewal": f"I'm checking the policy renewal. Processing: '{request.message}'",
        "fraud": f"Investigating fraud claim. Processing: '{request.message}'",
    }
    reply = mock_replies.get(request.agent, f"Hello! How can I help?")
    return ChatResponse(reply=reply, agent=request.agent)

@app.get("/api/agents")
async def list_agents():
    return [
        {"id": "appeal", "name": "Appeal Agent", "description": "Handle claim appeals"},
        {"id": "renewal", "name": "Renewal Agent", "description": "Policy renewal assessments"},
        {"id": "fraud", "name": "Fraud Agent", "description": "Fraud investigation"},
    ]

# ============================================================
# ADMIN ROUTES
# ============================================================

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    html = render_template("admin.html", {"request": request})
    return HTMLResponse(content=html)

# Tools Management
@app.get("/api/admin/tools")
async def get_tools():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tool_name, agent_name, enabled 
            FROM PlatformToolRegistry
            ORDER BY agent_name, tool_name
        """)
        rows = cursor.fetchall()
        return [{
            "tool_name": r[0],
            "agent_name": r[1],
            "enabled": bool(r[2]),
        } for r in rows]

@app.post("/api/admin/tools/toggle")
async def toggle_tool(data: ToolToggle):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE PlatformToolRegistry
            SET enabled = ?, updated_at = GETDATE()
            WHERE tool_name = ? AND agent_name = ?
        """, (1 if data.enabled else 0, data.tool_name, data.agent_name))
        conn.commit()
        return {"status": "updated"}

# RAG Documents Management
@app.get("/api/admin/documents")
async def get_documents():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, source, active, added_at FROM PlatformRAGDocuments ORDER BY added_at DESC")
        rows = cursor.fetchall()
        return [{
            "id": r[0],
            "name": r[1],
            "source": r[2],
            "active": bool(r[3]),
            "added_at": r[4],
        } for r in rows]

@app.post("/api/admin/documents")
async def add_document(data: RAGDocument):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO PlatformRAGDocuments (name, content, source, active)
            VALUES (?, ?, ?, ?)
        """, (data.name, data.content, data.source, 1 if data.active else 0))
        conn.commit()
        cursor.execute("SELECT SCOPE_IDENTITY()")
        return {"id": int(cursor.fetchone()[0]), "status": "added"}

@app.delete("/api/admin/documents/{doc_id}")
async def delete_document(doc_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE PlatformRAGDocuments
            SET active = 0, updated_at = GETDATE()
            WHERE id = ?
        """, (doc_id,))
        conn.commit()
        return {"status": "deleted"}

# HITL Tasks
@app.get("/api/admin/hitl")
async def get_hitl_tasks():
    return list_pending_hitl()

@app.get("/api/admin/hitl/{task_id}")
async def get_hitl_task_detail(task_id: int):
    task = get_hitl_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.post("/api/admin/hitl/{task_id}/resolve")
async def resolve_hitl_endpoint(task_id: int, decision: dict = {"action": "approved"}):
    try:
        resolve_hitl_task(task_id, decision)
        return {"status": "resolved", "task_id": task_id, "decision": decision}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Tickets
@app.get("/api/admin/tickets")
async def get_tickets():
    return list_open_tickets()

@app.get("/api/admin/tickets/{ticket_id}")
async def get_ticket_detail(ticket_id: int):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket

@app.post("/api/admin/tickets/{ticket_id}/resolve")
async def resolve_ticket_endpoint(ticket_id: int):
    try:
        resolve_ticket(ticket_id)
        return {"status": "resolved", "ticket_id": ticket_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)