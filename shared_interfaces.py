
"""
These functions create HITL tasks and tickets in the platform.
"""

from typing import Dict, Any, Optional


def create_hitl_task(
        graph_name: str,
        run_id: str,
        node_name: str,
        state: Dict[str, Any]
) -> int:
    """Create a HITL task and return its ID."""
    from platform.hitl import create_hitl_task as _create
    return _create(graph_name, run_id, node_name, state)


def create_ticket(
        graph_name: str,
        run_id: str,
        node_name: str,
        state: Dict[str, Any],
        error: str
) -> int:
    """Create a failure ticket and return its ID."""
    from platform.tickets import create_ticket as _create
    return _create(graph_name, run_id, node_name, state, error)


def save_checkpoint(
        graph_name: str,
        run_id: str,
        node_name: str,
        state: Dict[str, Any]
) -> None:
    """Save a graph checkpoint."""
    import json
    from platform.database import get_connection

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            MERGE INTO PlatformGraphCheckpoints AS target
            USING (VALUES (?, ?, ?, ?)) AS source (graph_name, run_id, node_name, state)
            ON target.graph_name = source.graph_name 
               AND target.run_id = source.run_id 
               AND target.node_name = source.node_name
            WHEN MATCHED THEN 
                UPDATE SET state = source.state, created_at = GETDATE()
            WHEN NOT MATCHED THEN 
                INSERT (graph_name, run_id, node_name, state) 
                VALUES (source.graph_name, source.run_id, source.node_name, source.state)
        """, (graph_name, run_id, node_name, json.dumps(state, default=str)))
        conn.commit()


def load_checkpoint(
        graph_name: str,
        run_id: str,
        node_name: str
) -> Optional[Dict[str, Any]]:
    """Load a graph checkpoint."""
    import json
    from platform.database import get_connection

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT state FROM PlatformGraphCheckpoints WHERE graph_name = ? AND run_id = ? AND node_name = ?",
            (graph_name, run_id, node_name)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None