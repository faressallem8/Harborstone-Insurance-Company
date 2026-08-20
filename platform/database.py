"""
SQL Server database connection and helpers for the platform.
Handles all database operations for tools, documents, HITL tasks, tickets, and checkpoints.
"""

import os
import pyodbc
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager


# ============================================================
# Database Helpers (using your existing pattern)
# ============================================================

def get_connection():
    """
    Get a SQL Server connection using Windows Authentication.
    Uses the same config as your MCP server.
    """
    server = os.getenv("WIN_DB_SERVER")
    database = os.getenv("WIN_DB_NAME")
    driver = os.getenv("WIN_DB_DRIVER")
    
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    
    return pyodbc.connect(conn_str)


def dict_to_json(d: Dict[str, Any]) -> str:
    """Convert dict to JSON string."""
    return json.dumps(d, default=str)


def json_to_dict(s: str) -> Dict[str, Any]:
    """Convert JSON string to dict."""
    if not s:
        return {}
    return json.loads(s)


def row_to_dict(cursor, row) -> Dict[str, Any]:
    """
    Convert a pyodbc row to dict with proper JSON parsing for state/decision columns.
    """
    if row is None:
        return None
    
    # Get column names from cursor description
    columns = [column[0] for column in cursor.description]
    
    # Build dict with JSON parsing
    result = {}
    for idx, col in enumerate(columns):
        value = row[idx]
        
        # Parse JSON fields (state and decision are NVARCHAR(MAX) storing JSON)
        if col in ['state', 'decision', 'resolution_notes'] and value is not None:
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass  # Keep as is if not valid JSON
        
        result[col] = value
    
    return result


# ============================================================
# HITL Tasks
# ============================================================

def get_pending_hitl_tasks() -> List[Dict]:
    """Get all pending HITL tasks."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, graph_name, run_id, node_name, state, 
                   status, assigned_to, created_at, resolved_at,
                   decision, priority, resolution_notes
            FROM PlatformHITLTasks
            WHERE status = 'pending'
            ORDER BY 
                CASE priority 
                    WHEN 'urgent' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                created_at ASC
        """)
        rows = cursor.fetchall()
        return [row_to_dict(cursor, row) for row in rows]


def create_hitl_task(
    graph_name: str,
    run_id: str,
    node_name: str,
    state: Dict,
    assigned_to: str = None,
    priority: str = 'medium'
) -> Dict:
    """Create a new HITL task."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO PlatformHITLTasks 
            (graph_name, run_id, node_name, state, assigned_to, priority)
            OUTPUT INSERTED.*
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            graph_name,
            run_id,
            node_name,
            dict_to_json(state),
            assigned_to,
            priority
        ))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)


def resolve_hitl_task(
    task_id: int,
    decision: Dict,
    status: str = 'resolved',
    resolution_notes: str = None
) -> Dict:
    """
    Resolve a HITL task with decision and resolution notes.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE PlatformHITLTasks
            SET status = ?,
                decision = ?,
                resolution_notes = ?,
                resolved_at = GETDATE()
            OUTPUT INSERTED.*
            WHERE id = ?
        """, (
            status,
            dict_to_json(decision),
            resolution_notes,
            task_id
        ))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)


def get_hitl_task(task_id: int) -> Optional[Dict]:
    """Get a specific HITL task by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, graph_name, run_id, node_name, state, 
                   status, assigned_to, created_at, resolved_at,
                   decision, priority, resolution_notes
            FROM PlatformHITLTasks
            WHERE id = ?
        """, (task_id,))
        row = cursor.fetchone()
        return row_to_dict(cursor, row) if row else None


# ============================================================
# Tickets
# ============================================================

def get_open_tickets() -> List[Dict]:
    """Get all open tickets."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, graph_name, run_id, node_name, state, 
                   error_message, error_type, status, assigned_to, 
                   created_at, resolved_at, resolution_notes, severity
            FROM PlatformTickets
            WHERE status IN ('open', 'investigating')
            ORDER BY 
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                created_at ASC
        """)
        rows = cursor.fetchall()
        return [row_to_dict(cursor, row) for row in rows]


def create_ticket(
    graph_name: str,
    run_id: str,
    node_name: str,
    state: Dict,
    error_message: str,
    error_type: str = None,
    assigned_to: str = None,
    severity: str = 'medium'
) -> Dict:
    """Create a new ticket."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO PlatformTickets 
            (graph_name, run_id, node_name, state, error_message, 
             error_type, assigned_to, severity)
            OUTPUT INSERTED.*
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            graph_name,
            run_id,
            node_name,
            dict_to_json(state),
            error_message,
            error_type,
            assigned_to,
            severity
        ))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)


def resolve_ticket(ticket_id: int, status: str, resolution_notes: str) -> Dict:
    """Resolve a ticket."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE PlatformTickets
            SET status = ?,
                resolution_notes = ?,
                resolved_at = GETDATE()
            OUTPUT INSERTED.*
            WHERE id = ?
        """, (status, resolution_notes, ticket_id))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)


def get_ticket(ticket_id: int) -> Optional[Dict]:
    """Get a specific ticket by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, graph_name, run_id, node_name, state, 
                   error_message, error_type, status, assigned_to, 
                   created_at, resolved_at, resolution_notes, severity
            FROM PlatformTickets
            WHERE id = ?
        """, (ticket_id,))
        row = cursor.fetchone()
        return row_to_dict(cursor, row) if row else None


# ============================================================
# Checkpoints
# ============================================================

def save_checkpoint(graph_name: str, run_id: str, node_name: str, state: Dict) -> Dict:
    """Save a graph checkpoint."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            MERGE INTO PlatformGraphCheckpoints AS target
            USING (SELECT ? AS graph_name, ? AS run_id, ? AS node_name) AS source
            ON (target.graph_name = source.graph_name 
                AND target.run_id = source.run_id 
                AND target.node_name = source.node_name)
            WHEN MATCHED THEN
                UPDATE SET state = ?, created_at = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (graph_name, run_id, node_name, state)
                VALUES (?, ?, ?, ?)
            OUTPUT INSERTED.*;
        """, (
            graph_name, run_id, node_name,
            dict_to_json(state),
            graph_name, run_id, node_name, dict_to_json(state)
        ))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)


def get_checkpoint(graph_name: str, run_id: str, node_name: str) -> Optional[Dict]:
    """Get a specific checkpoint."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, graph_name, run_id, node_name, state, created_at
            FROM PlatformGraphCheckpoints
            WHERE graph_name = ? AND run_id = ? AND node_name = ?
        """, (graph_name, run_id, node_name))
        row = cursor.fetchone()
        return row_to_dict(cursor, row) if row else None


def get_latest_checkpoint(graph_name: str, run_id: str) -> Optional[Dict]:
    """Get the latest checkpoint for a run."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP 1 id, graph_name, run_id, node_name, state, created_at
            FROM PlatformGraphCheckpoints
            WHERE graph_name = ? AND run_id = ?
            ORDER BY created_at DESC, id DESC
        """, (graph_name, run_id))
        row = cursor.fetchone()
        return row_to_dict(cursor, row) if row else None


def delete_checkpoint(graph_name: str, run_id: str, node_name: str) -> bool:
    """Delete a checkpoint."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM PlatformGraphCheckpoints
            WHERE graph_name = ? AND run_id = ? AND node_name = ?
        """, (graph_name, run_id, node_name))
        return cursor.rowcount > 0


def delete_checkpoints_for_run(graph_name: str, run_id: str) -> int:
    """Delete all checkpoints for a run."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM PlatformGraphCheckpoints
            WHERE graph_name = ? AND run_id = ?
        """, (graph_name, run_id))
        return cursor.rowcount


# ============================================================
# Tool Registry
# ============================================================

def get_all_tools() -> List[Dict]:
    """Get all tool registry entries."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, tool_name, agent_name, enabled, 
                   created_at, updated_at
            FROM PlatformToolRegistry
            ORDER BY tool_name, agent_name
        """)
        rows = cursor.fetchall()
        return [row_to_dict(cursor, row) for row in rows]


def get_tools_for_agent(agent_name: str, enabled_only: bool = True) -> List[Dict]:
    """Get tools for a specific agent."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT id, tool_name, agent_name, enabled, 
                   created_at, updated_at
            FROM PlatformToolRegistry
            WHERE agent_name = ?
        """
        params = [agent_name]
        if enabled_only:
            query += " AND enabled = 1"
        query += " ORDER BY tool_name"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [row_to_dict(cursor, row) for row in rows]


def register_tool(tool_name: str, agent_name: str, enabled: bool = True) -> Dict:
    """Register a tool for an agent."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO PlatformToolRegistry 
            (tool_name, agent_name, enabled)
            OUTPUT INSERTED.*
            VALUES (?, ?, ?)
        """, (tool_name, agent_name, enabled))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)


def update_tool(tool_id: int, enabled: bool) -> Dict:
    """Update a tool's status."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE PlatformToolRegistry
            SET enabled = ?,
                updated_at = GETDATE()
            OUTPUT INSERTED.*
            WHERE id = ?
        """, (enabled, tool_id))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)


def delete_tool(tool_id: int) -> bool:
    """Delete a tool registry entry."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM PlatformToolRegistry WHERE id = ?", (tool_id,))
        return cursor.rowcount > 0


def get_tool_by_name_and_agent(tool_name: str, agent_name: str) -> Optional[Dict]:
    """Get a specific tool for an agent."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, tool_name, agent_name, enabled, 
                   created_at, updated_at
            FROM PlatformToolRegistry
            WHERE tool_name = ? AND agent_name = ?
        """, (tool_name, agent_name))
        row = cursor.fetchone()
        return row_to_dict(cursor, row) if row else None


def get_agent_tool_names(agent_name: str) -> List[str]:
    """Get all enabled tool names for an agent."""
    tools = get_tools_for_agent(agent_name, enabled_only=True)
    return [tool['tool_name'] for tool in tools]


# ============================================================
# RAG Documents
# ============================================================

def get_all_documents(active_only: bool = True) -> List[Dict]:
    """Get all RAG documents."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT id, name, content, source, active, 
                   added_at, updated_at
            FROM PlatformRAGDocuments
        """
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY name"
        
        cursor.execute(query)
        rows = cursor.fetchall()
        return [row_to_dict(cursor, row) for row in rows]


def add_document(name: str, content: str, source: str = None, active: bool = True) -> Dict:
    """Add a new RAG document."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO PlatformRAGDocuments 
            (name, content, source, active)
            OUTPUT INSERTED.*
            VALUES (?, ?, ?, ?)
        """, (name, content, source, active))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)


def update_document_status(doc_id: int, active: bool) -> Dict:
    """Update a document's status."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE PlatformRAGDocuments
            SET active = ?,
                updated_at = GETDATE()
            OUTPUT INSERTED.*
            WHERE id = ?
        """, (active, doc_id))
        row = cursor.fetchone()
        return row_to_dict(cursor, row)


def delete_document(doc_id: int) -> bool:
    """Delete a document."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM PlatformRAGDocuments WHERE id = ?", (doc_id,))
        return cursor.rowcount > 0


def get_document_by_name(name: str) -> Optional[Dict]:
    """Get a document by name."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, content, source, active, added_at, updated_at
            FROM PlatformRAGDocuments
            WHERE name = ?
        """, (name,))
        row = cursor.fetchone()
        return row_to_dict(cursor, row) if row else None


def get_active_documents() -> List[Dict]:
    """Get all active documents."""
    return get_all_documents(active_only=True)


def count_documents(active_only: bool = True) -> int:
    """Count documents."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT COUNT(*) FROM PlatformRAGDocuments"
        if active_only:
            query += " WHERE active = 1"
        cursor.execute(query)
        return cursor.fetchone()[0]
    
def get_tool_by_id(tool_id: int) -> Optional[Dict]:
    """Get a tool registry entry by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, tool_name, agent_name, enabled, 
                   created_at, updated_at
            FROM PlatformToolRegistry
            WHERE id = ?
        """, (tool_id,))
        row = cursor.fetchone()
        return row_to_dict(cursor, row) if row else None