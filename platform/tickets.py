
"""Failure ticket management."""

import json
from typing import Dict, Any, List, Optional
from platform.database import get_connection

def create_ticket(
    graph_name: str,
    run_id: str,
    node_name: str,
    state: Dict[str, Any],
    error: str
) -> int:
    """Create a failure ticket and return its ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO PlatformTickets (graph_name, run_id, node_name, state, error_message, status)
            VALUES (?, ?, ?, ?, ?, 'open')
        """, (graph_name, run_id, node_name, json.dumps(state, default=str), error))
        conn.commit()
        cursor.execute("SELECT SCOPE_IDENTITY()")
        return int(cursor.fetchone()[0])

def get_ticket(ticket_id: int) -> Optional[Dict]:
    """Get a ticket by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM PlatformTickets WHERE id = ?", (ticket_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "graph_name": row[1],
            "run_id": row[2],
            "node_name": row[3],
            "state": json.loads(row[4]) if row[4] else {},
            "error_message": row[5],
            "status": row[6],
            "assigned_to": row[7],
            "created_at": row[8],
            "resolved_at": row[9],
        }

def list_open_tickets() -> List[Dict]:
    """List all open tickets."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM PlatformTickets 
            WHERE status IN ('open', 'investigating') 
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return [{
            "id": r[0],
            "graph_name": r[1],
            "run_id": r[2],
            "node_name": r[3],
            "state": json.loads(r[4]) if r[4] else {},
            "error_message": r[5],
            "status": r[6],
            "created_at": r[8],
        } for r in rows]

def resolve_ticket(ticket_id: int) -> None:
    """Mark a ticket as resolved."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE PlatformTickets
            SET status = 'resolved', resolved_at = GETDATE()
            WHERE id = ?
        """, (ticket_id,))
        conn.commit()