"""
Tests for database operations.
Run with: pytest tests/test_database.py -v
"""

import sys
import asyncio  # ← أضف هذا
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pytest

from platform.database import (
    get_connection,
    get_pending_hitl_tasks,
    create_hitl_task,
    resolve_hitl_task,
    get_hitl_task,
    get_open_tickets,
    create_ticket,
    resolve_ticket,
    get_ticket,
    save_checkpoint,
    get_checkpoint,
    get_latest_checkpoint,
    get_all_tools,
    get_tools_for_agent,
    register_tool,
    update_tool,
    delete_tool,
    get_all_documents,
    add_document,
    update_document_status,
    delete_document,
)


class TestDatabaseConnection:
    """Test database connection"""

    def test_connection(self):
        """Test that we can connect to the database"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT @@VERSION")
                version = cursor.fetchone()
                assert version is not None
                print(f"✅ Connected to SQL Server")
        except Exception as e:
            pytest.fail(f"Database connection failed: {e}")

    def test_tables_exist(self):
        """Test that platform tables exist"""
        with get_connection() as conn:
            cursor = conn.cursor()
            tables = [
                "PlatformHITLTasks",
                "PlatformTickets",
                "PlatformGraphCheckpoints",
                "PlatformToolRegistry",
                "PlatformRAGDocuments"
            ]
            for table in tables:
                cursor.execute("""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_NAME = ?
                """, (table,))
                count = cursor.fetchone()[0]
                assert count == 1, f"Table {table} does not exist"
                print(f"✅ Table {table} exists")

    def test_columns_exist(self):
        """Test that all required columns exist"""
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # PlatformHITLTasks columns
            cursor.execute("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'PlatformHITLTasks'
            """)
            columns = [row[0] for row in cursor.fetchall()]
            required = ['id', 'graph_name', 'run_id', 'node_name', 'state', 
                       'status', 'decision', 'priority', 'resolution_notes']
            for col in required:
                assert col in columns, f"Column {col} not found in PlatformHITLTasks"
            print("✅ PlatformHITLTasks columns OK")
            
            # PlatformTickets columns
            cursor.execute("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'PlatformTickets'
            """)
            columns = [row[0] for row in cursor.fetchall()]
            required = ['id', 'graph_name', 'run_id', 'node_name', 'state', 
                       'error_message', 'error_type', 'status', 'resolution_notes', 'severity']
            for col in required:
                assert col in columns, f"Column {col} not found in PlatformTickets"
            print("✅ PlatformTickets columns OK")


class TestHITLTasks:
    """Test HITL operations"""

    def test_create_hitl_task(self):
        """Test creating a HITL task"""
        state = {"claim_id": 123, "amount": 15000, "status": "pending_review"}
        
        task = create_hitl_task(
            graph_name="test_graph",
            run_id="test_run_123",
            node_name="underwriter_review",
            state=state,
            assigned_to="admin",
            priority="high"
        )
        
        assert task is not None
        assert task['graph_name'] == "test_graph"
        assert task['run_id'] == "test_run_123"
        assert task['node_name'] == "underwriter_review"
        assert task['status'] == "pending"
        assert task['priority'] == "high"
        assert task['state'] == state
        print(f"✅ HITL task created: ID {task['id']}")
        
        # Cleanup
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PlatformHITLTasks WHERE id = ?", (task['id'],))
            conn.commit()

    def test_get_pending_hitl_tasks(self):
        """Test getting pending HITL tasks"""
        # Create a task
        state = {"claim_id": 456, "amount": 25000}
        task = create_hitl_task(
            graph_name="test_graph",
            run_id="test_run_456",
            node_name="underwriter_review",
            state=state
        )
        
        # Get pending tasks
        tasks = get_pending_hitl_tasks()
        assert len(tasks) > 0
        
        # Cleanup
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PlatformHITLTasks WHERE id = ?", (task['id'],))
            conn.commit()
        print("✅ Pending HITL tasks retrieved")

    def test_resolve_hitl_task(self):
        """Test resolving a HITL task"""
        # Create a task
        state = {"claim_id": 789, "amount": 50000}
        task = create_hitl_task(
            graph_name="test_graph",
            run_id="test_run_789",
            node_name="underwriter_review",
            state=state
        )
        
        # Resolve it
        decision = {"action": "approved", "notes": "Claim approved"}
        resolved = resolve_hitl_task(task['id'], decision, "resolved", "Approved by admin")
        
        assert resolved['status'] == "resolved"
        assert resolved['decision'] == decision
        print(f"✅ HITL task resolved: ID {task['id']}")
        
        # Cleanup
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PlatformHITLTasks WHERE id = ?", (task['id'],))
            conn.commit()


class TestTickets:
    """Test ticket operations"""

    def test_create_ticket(self):
        """Test creating a ticket"""
        state = {"claim_id": 111, "stage": "submission"}
        
        ticket = create_ticket(
            graph_name="test_graph",
            run_id="test_run_111",
            node_name="submit_claim",
            state=state,
            error_message="Failed to connect to external API",
            error_type="connection_error",
            assigned_to="admin",
            severity="high"
        )
        
        assert ticket is not None
        assert ticket['graph_name'] == "test_graph"
        assert ticket['run_id'] == "test_run_111"
        assert ticket['error_message'] == "Failed to connect to external API"
        assert ticket['status'] == "open"
        assert ticket['severity'] == "high"
        print(f"✅ Ticket created: ID {ticket['id']}")
        
        # Cleanup
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PlatformTickets WHERE id = ?", (ticket['id'],))
            conn.commit()

    def test_resolve_ticket(self):
        """Test resolving a ticket"""
        # Create a ticket
        ticket = create_ticket(
            graph_name="test_graph",
            run_id="test_run_222",
            node_name="process_claim",
            state={"claim_id": 222},
            error_message="Validation failed"
        )
        
        # Resolve it
        resolved = resolve_ticket(ticket['id'], "resolved", "Fixed validation rules")
        
        assert resolved['status'] == "resolved"
        assert resolved['resolution_notes'] == "Fixed validation rules"
        print(f"✅ Ticket resolved: ID {ticket['id']}")
        
        # Cleanup
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PlatformTickets WHERE id = ?", (ticket['id'],))
            conn.commit()


class TestCheckpoints:
    """Test checkpoint operations"""

    def test_save_checkpoint(self):
        """Test saving a checkpoint"""
        state = {"claim_id": 333, "node": "review", "progress": 50}
        
        checkpoint = save_checkpoint(
            graph_name="test_graph",
            run_id="test_run_333",
            node_name="review_node",
            state=state
        )
        
        assert checkpoint is not None
        assert checkpoint['graph_name'] == "test_graph"
        assert checkpoint['run_id'] == "test_run_333"
        assert checkpoint['node_name'] == "review_node"
        assert checkpoint['state'] == state
        print(f"✅ Checkpoint saved: ID {checkpoint['id']}")

    def test_get_checkpoint(self):
        """Test getting a checkpoint"""
        state = {"claim_id": 444, "node": "approval", "progress": 100}
        
        # Save
        checkpoint = save_checkpoint(
            graph_name="test_graph",
            run_id="test_run_444",
            node_name="approval_node",
            state=state
        )
        
        # Get
        retrieved = get_checkpoint("test_graph", "test_run_444", "approval_node")
        assert retrieved is not None
        assert retrieved['state'] == state
        print(f"✅ Checkpoint retrieved: ID {retrieved['id']}")

    def test_get_latest_checkpoint(self):
        """Test getting the latest checkpoint"""
        # Save multiple checkpoints
        save_checkpoint("test_graph", "test_run_555", "node_1", {"step": 1})
        save_checkpoint("test_graph", "test_run_555", "node_2", {"step": 2})
        save_checkpoint("test_graph", "test_run_555", "node_3", {"step": 3})
        
        # Get latest
        latest = get_latest_checkpoint("test_graph", "test_run_555")
        assert latest is not None
        assert latest['node_name'] == "node_3"
        assert latest['state']['step'] == 3
        print(f"✅ Latest checkpoint: {latest['node_name']}")


class TestToolRegistry:
    """Test tool registry operations"""

    def test_get_all_tools(self):
        """Test getting all tools"""
        tools = get_all_tools()
        assert len(tools) > 0
        print(f"✅ {len(tools)} tools found in registry")

    def test_get_tools_for_agent(self):
        """Test getting tools for a specific agent"""
        tools = get_tools_for_agent("Appeal Agent", enabled_only=True)
        assert len(tools) > 0
        for tool in tools:
            assert tool['enabled'] == True
        print(f"✅ {len(tools)} tools for Appeal Agent")

    def test_register_tool(self):
        """Test registering a new tool"""
        tool = register_tool("test_tool", "Test Agent", True)
        assert tool['tool_name'] == "test_tool"
        assert tool['agent_name'] == "Test Agent"
        assert tool['enabled'] == True
        print(f"✅ Tool registered: ID {tool['id']}")
        
        # Cleanup
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PlatformToolRegistry WHERE id = ?", (tool['id'],))
            conn.commit()

    def test_update_tool(self):
        """Test updating a tool"""
        # Create
        tool = register_tool("test_tool_2", "Test Agent", True)
        
        # Update
        updated = update_tool(tool['id'], False)
        assert updated['enabled'] == False
        print(f"✅ Tool updated: {tool['id']} -> enabled=False")
        
        # Cleanup
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PlatformToolRegistry WHERE id = ?", (tool['id'],))
            conn.commit()

    def test_delete_tool(self):
        """Test deleting a tool"""
        # Create
        tool = register_tool("test_tool_3", "Test Agent", True)
        
        # Delete
        deleted = delete_tool(tool['id'])
        assert deleted == True
        print(f"✅ Tool deleted: ID {tool['id']}")


class TestRAGDocuments:
    """Test RAG document operations"""

    def test_get_all_documents(self):
        """Test getting all documents"""
        docs = get_all_documents()
        assert len(docs) >= 1
        print(f"✅ {len(docs)} documents found")

    def test_add_document(self):
        """Test adding a document"""
        doc = add_document(
            name="Test Document",
            content="This is a test document content.",
            source="test_source",
            active=True
        )
        
        assert doc['name'] == "Test Document"
        assert doc['content'] == "This is a test document content."
        assert doc['active'] == True
        print(f"✅ Document added: ID {doc['id']}")
        
        # Cleanup
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PlatformRAGDocuments WHERE id = ?", (doc['id'],))
            conn.commit()

    def test_update_document_status(self):
        """Test updating document status"""
        # Create
        doc = add_document("Test Doc 2", "Content", "test", True)
        
        # Update
        updated = update_document_status(doc['id'], False)
        assert updated['active'] == False
        print(f"✅ Document status updated: ID {doc['id']} -> inactive")
        
        # Cleanup
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PlatformRAGDocuments WHERE id = ?", (doc['id'],))
            conn.commit()

    def test_delete_document(self):
        """Test deleting a document"""
        # Create
        doc = add_document("Test Doc 3", "Content", "test", True)
        
        # Delete
        deleted = delete_document(doc['id'])
        assert deleted == True
        print(f"✅ Document deleted: ID {doc['id']}")


class TestDynamicRegistry:
    """Test dynamic tool registry behavior"""

    def test_dynamic_tool_registry_flow(self):
        """Test full dynamic registry flow: register -> disable -> enable -> delete"""
        print("\n--- Testing Dynamic Registry Flow ---")
        
        async def run_test():
            from platform.database import register_tool, update_tool, delete_tool, get_tools_for_agent
            
            agent_name = "Test Dynamic Agent"
            tool_name = "test_dynamic_registry_tool"
            
            # 1. Register tool
            tool = register_tool(tool_name, agent_name, enabled=True)
            assert tool is not None
            assert tool["tool_name"] == tool_name
            assert tool["agent_name"] == agent_name
            assert tool["enabled"] == True
            print(f"✅ Tool registered: {tool_name}")
            
            # 2. Verify tool is in agent's list
            tools = get_tools_for_agent(agent_name, enabled_only=True)
            found = any(t["tool_name"] == tool_name for t in tools)
            assert found == True
            print(f"✅ Tool found in agent's list")
            
            # 3. Disable tool
            updated = update_tool(tool["id"], enabled=False)
            assert updated["enabled"] == False
            print(f"✅ Tool disabled")
            
            # 4. Verify tool is not in enabled list
            tools = get_tools_for_agent(agent_name, enabled_only=True)
            found = any(t["tool_name"] == tool_name for t in tools)
            assert found == False
            print(f"✅ Tool not in enabled list")
            
            # 5. Re-enable tool
            updated = update_tool(tool["id"], enabled=True)
            assert updated["enabled"] == True
            print(f"✅ Tool re-enabled")
            
            # 6. Verify tool is back in enabled list
            tools = get_tools_for_agent(agent_name, enabled_only=True)
            found = any(t["tool_name"] == tool_name for t in tools)
            assert found == True
            print(f"✅ Tool back in enabled list")
            
            # 7. Delete tool
            deleted = delete_tool(tool["id"])
            assert deleted == True
            print(f"✅ Tool deleted")
            
            # 8. Verify tool is gone
            tools = get_tools_for_agent(agent_name, enabled_only=False)
            found = any(t["tool_name"] == tool_name for t in tools)
            assert found == False
            print(f"✅ Tool removed from registry")
            
            print("✅ Dynamic Registry Flow test passed!")
        
        asyncio.run(run_test())


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])