
"""Failure ticket management."""

import json
from typing import Dict, Any, List, Optional
from web_platform.database import get_connection


def create_ticket(
    graph_name: str,
    run_id: str,
    node_name: str,
    state: Dict[str, Any],
    error_message: str,
    error_type: str = None,
    assigned_to: str = None,
    severity: str = 'medium'
) -> int:
    """Create a failure ticket and return its ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Use OUTPUT INSERTED.* to get the ID directly
        cursor.execute("""
            INSERT INTO PlatformTickets 
            (graph_name, run_id, node_name, state, error_message, 
             error_type, assigned_to, severity, status)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')
        """, (
            graph_name,
            run_id,
            node_name,
            json.dumps(state, default=str),
            error_message,
            error_type,
            assigned_to,
            severity
        ))
        
        row = cursor.fetchone()
        if row and row[0] is not None:
            return int(row[0])
        else:
            # Fallback: use SCOPE_IDENTITY()
            cursor.execute("SELECT SCOPE_IDENTITY()")
            identity = cursor.fetchone()
            if identity and identity[0] is not None:
                return int(identity[0])
            raise RuntimeError("Failed to get ID for created ticket")


def get_ticket(ticket_id: int) -> Optional[Dict]:
    """Get a ticket by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, graph_name, run_id, node_name, state, error_message,
                   error_type, status, assigned_to, created_at, resolved_at,
                   resolution_notes, severity
            FROM PlatformTickets 
            WHERE id = ?
        """, (ticket_id,))
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
            "error_type": row[6],
            "status": row[7],
            "assigned_to": row[8],
            "created_at": row[9],
            "resolved_at": row[10],
            "resolution_notes": row[11],
            "severity": row[12],
        }


def list_open_tickets() -> List[Dict]:
    """List all open tickets."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, graph_name, run_id, node_name, state, error_message,
                   error_type, status, assigned_to, created_at, severity
            FROM PlatformTickets 
            WHERE status IN ('open', 'investigating') 
            ORDER BY 
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                created_at DESC
        """)
        rows = cursor.fetchall()
        return [{
            "id": r[0],
            "graph_name": r[1],
            "run_id": r[2],
            "node_name": r[3],
            "state": json.loads(r[4]) if r[4] else {},
            "error_message": r[5],
            "error_type": r[6],
            "status": r[7],
            "assigned_to": r[8],
            "created_at": r[9],
            "severity": r[10],
        } for r in rows]


def resolve_ticket(ticket_id: int, resolution_notes: str = None) -> None:
    """Mark a ticket as resolved."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE PlatformTickets
            SET status = 'resolved', 
                resolution_notes = ?,
                resolved_at = GETDATE()
            WHERE id = ?
        """, (resolution_notes, ticket_id))
        conn.commit()