"""HITL (Human-in-the-Loop) task management."""

import json
from typing import Dict, Any, List, Optional
from platform.database import get_connection


def create_hitl_task(
    graph_name: str,
    run_id: str,
    node_name: str,
    state: Dict[str, Any],
    assigned_to: str = None,
    priority: str = 'medium'
) -> int:
    """Create a HITL task and return its ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO PlatformHITLTasks 
            (graph_name, run_id, node_name, state, status, assigned_to, priority)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
        """, (
            graph_name, 
            run_id, 
            node_name, 
            json.dumps(state, default=str),
            assigned_to,
            priority
        ))
        conn.commit()
        cursor.execute("SELECT SCOPE_IDENTITY()")
        return int(cursor.fetchone()[0])


def get_hitl_task(task_id: int) -> Optional[Dict]:
    """Get a HITL task by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, graph_name, run_id, node_name, state, status, 
                   assigned_to, created_at, resolved_at, decision, priority, resolution_notes
            FROM PlatformHITLTasks 
            WHERE id = ?
        """, (task_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "graph_name": row[1],
            "run_id": row[2],
            "node_name": row[3],
            "state": json.loads(row[4]) if row[4] else {},
            "status": row[5],
            "assigned_to": row[6],
            "created_at": row[7],
            "resolved_at": row[8],
            "decision": json.loads(row[9]) if row[9] else None,
            "priority": row[10],
            "resolution_notes": row[11],
        }


def list_pending_hitl() -> List[Dict]:
    """List all pending HITL tasks."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, graph_name, run_id, node_name, state, status, 
                   assigned_to, created_at, priority
            FROM PlatformHITLTasks 
            WHERE status = 'pending' 
            ORDER BY 
                CASE priority 
                    WHEN 'urgent' THEN 1
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
            "status": r[5],
            "assigned_to": r[6],
            "created_at": r[7],
            "priority": r[8],
        } for r in rows]


def resolve_hitl_task(task_id: int, decision: Dict[str, Any], resolution_notes: str = None) -> None:
    """Resolve a HITL task with the admin's decision."""
    with get_connection() as conn:
        cursor = conn.cursor()
        task = get_hitl_task(task_id)
        if not task:
            raise ValueError(f"HITL task {task_id} not found")

        cursor.execute("""
            UPDATE PlatformHITLTasks
            SET status = 'resolved', 
                decision = ?, 
                resolution_notes = ?,
                resolved_at = GETDATE()
            WHERE id = ?
        """, (json.dumps(decision, default=str), resolution_notes, task_id))
        conn.commit()