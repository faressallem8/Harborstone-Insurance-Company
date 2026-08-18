
"""HITL (Human-in-the-Loop) task management."""

import json
from typing import Dict, Any, List, Optional
from platform.database import get_connection


def create_hitl_task(
        graph_name: str,
        run_id: str,
        node_name: str,
        state: Dict[str, Any]
) -> int:
    """Create a HITL task and return its ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO PlatformHITLTasks (graph_name, run_id, node_name, state, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (graph_name, run_id, node_name, json.dumps(state, default=str)))
        conn.commit()
        cursor.execute("SELECT SCOPE_IDENTITY()")
        return int(cursor.fetchone()[0])


def get_hitl_task(task_id: int) -> Optional[Dict]:
    """Get a HITL task by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM PlatformHITLTasks WHERE id = ?", (task_id,))
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
        }


def list_pending_hitl() -> List[Dict]:
    """List all pending HITL tasks."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM PlatformHITLTasks 
            WHERE status = 'pending' 
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        return [{
            "id": r[0],
            "graph_name": r[1],
            "run_id": r[2],
            "node_name": r[3],
            "state": json.loads(r[4]) if r[4] else {},
            "status": r[5],
            "created_at": r[7],
        } for r in rows]


def resolve_hitl_task(task_id: int, decision: Dict[str, Any]) -> None:
    """Resolve a HITL task with the admin's decision."""
    with get_connection() as conn:
        cursor = conn.cursor()
        task = get_hitl_task(task_id)
        if not task:
            raise ValueError(f"HITL task {task_id} not found")

        state = task["state"]
        state["hitl_decision"] = decision

        cursor.execute("""
            UPDATE PlatformHITLTasks
            SET status = 'resolved', state = ?, resolved_at = GETDATE()
            WHERE id = ?
        """, (json.dumps(state, default=str), task_id))
        conn.commit()