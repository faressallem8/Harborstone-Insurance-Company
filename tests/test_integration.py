"""
Integration tests for the web_platform.
Run with: pytest tests/test_integration.py -v
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pytest

try:
    from fastapi.testclient import TestClient
    from web_platform.app import app
    from web_platform.database import get_connection
    client = TestClient(app)
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("⚠️ FastAPI not installed. Skipping integration tests.")
except Exception as e:
    FASTAPI_AVAILABLE = False
    print(f"⚠️ Error: {e}")


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestIntegration:
    """End-to-end integration tests"""

    def test_full_hitl_flow(self):
        """Test full HITL flow: create -> list -> resolve"""
        print("\n--- Testing HITL Flow ---")
        
        # 1. Create HITL task
        response = client.post("/api/hitl", json={
            "graph_name": "integration_test",
            "run_id": "integration_run_001",
            "node_name": "underwriter_review",
            "state": {"claim_id": 1001, "amount": 25000},
            "priority": "high"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        task_id = data["data"]["id"]
        print(f"✅ HITL task created: ID {task_id}")
        
        # 2. List pending tasks
        response = client.get("/api/admin/hitl")
        assert response.status_code == 200
        data = response.json()
        tasks = data["data"]["tasks"]
        assert len(tasks) > 0
        print(f"✅ HITL tasks listed: {len(tasks)} found")
        
        # 3. Resolve HITL task
        response = client.post(f"/api/admin/hitl/{task_id}/resolve", json={
            "decision": {"action": "approved", "notes": "Approved by admin"},
            "status": "resolved"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        print(f"✅ HITL task resolved: ID {task_id}")
        
        # Cleanup
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PlatformHITLTasks WHERE id = ?", (task_id,))
            conn.commit()
        print("✅ HITL Flow test passed!")

    def test_full_ticket_flow(self):
        """Test full ticket flow: create -> list -> resolve"""
        print("\n--- Testing Ticket Flow ---")
        
        # 1. Create ticket
        response = client.post("/api/tickets", json={
            "graph_name": "integration_test",
            "run_id": "integration_run_002",
            "node_name": "submit_claim",
            "state": {"claim_id": 1002},
            "error_message": "API timeout: external service unavailable",
            "error_type": "timeout",
            "severity": "high"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        ticket_id = data["data"]["id"]
        print(f"✅ Ticket created: ID {ticket_id}")
        
        # 2. List open tickets
        response = client.get("/api/admin/tickets")
        assert response.status_code == 200
        data = response.json()
        tickets = data["data"]["tickets"]
        assert len(tickets) > 0
        print(f"✅ Tickets listed: {len(tickets)} found")
        
        # 3. Resolve ticket
        response = client.post(f"/api/admin/tickets/{ticket_id}/resolve", json={
            "status": "resolved",
            "resolution_notes": "Fixed API connection issue"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        print(f"✅ Ticket resolved: ID {ticket_id}")
        
        # Cleanup
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PlatformTickets WHERE id = ?", (ticket_id,))
            conn.commit()
        print("✅ Ticket Flow test passed!")

    def test_full_checkpoint_flow(self):
        """Test full checkpoint flow: save -> get -> latest"""
        print("\n--- Testing Checkpoint Flow ---")
        
        graph_name = "integration_test"
        run_id = "integration_run_003"
        
        # 1. Save multiple checkpoints
        for i in range(1, 4):
            response = client.post(
                "/api/checkpoints",
                json={
                    "graph_name": graph_name,
                    "run_id": run_id,
                    "node_name": f"node_{i}",
                    "state": {"step": i, "data": f"step_{i}_data"}
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            print(f"✅ Checkpoint saved: node_{i}")
        
        # 2. Get specific checkpoint
        response = client.get(f"/api/checkpoints/{graph_name}/{run_id}/node_2")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["state"]["step"] == 2
        print(f"✅ Checkpoint retrieved: node_2")
        
        # 3. Get latest checkpoint
        response = client.get(f"/api/checkpoints/{graph_name}/{run_id}/latest")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["node_name"] == "node_3"
        assert data["data"]["state"]["step"] == 3
        print(f"✅ Latest checkpoint: node_3")
        
        # Cleanup
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM PlatformGraphCheckpoints WHERE graph_name = ? AND run_id = ?",
                (graph_name, run_id)
            )
            conn.commit()
        print("✅ Checkpoint Flow test passed!")

    def test_tool_toggle_effect(self):
        """Test that toggling a tool affects the agent"""
        print("\n--- Testing Tool Toggle Effect ---")
        
        # 1. Get initial tools for Appeal Agent
        response = client.get("/api/admin/tools/agent/Appeal%20Agent")
        assert response.status_code == 200
        initial = response.json()
        tools = initial["data"]["tools"]
        assert len(tools) > 0
        print(f"✅ Initial tools: {len(tools)}")
        
        # Find a tool to toggle
        tool = next((t for t in tools if t["tool_name"] == "approve_claim"), None)
        if tool:
            tool_id = tool["id"]
            
            # 2. Disable the tool
            response = client.put(f"/api/admin/tools/{tool_id}", json={"enabled": False})
            assert response.status_code == 200
            
            # 3. Get tools again
            response = client.get("/api/admin/tools/agent/Appeal%20Agent")
            assert response.status_code == 200
            updated = response.json()
            updated_tools = updated["data"]["tools"]
            
            # 4. Verify the tool is now disabled
            updated_tool = next((t for t in updated_tools if t["id"] == tool_id), None)
            if updated_tool:
                assert updated_tool["enabled"] == False
                print(f"✅ Tool {tool['tool_name']} disabled")
            
            # 5. Re-enable
            response = client.put(f"/api/admin/tools/{tool_id}", json={"enabled": True})
            assert response.status_code == 200
            print(f"✅ Tool {tool['tool_name']} re-enabled")
        else:
            print("⚠️ No toggleable tool found")
        
        print("✅ Tool Toggle test passed!")

    def test_chat_with_agent(self):
        """Test chatting with an agent"""
        print("\n--- Testing Chat ---")
        
        # 1. List agents
        response = client.get("/api/agents")
        assert response.status_code == 200
        agents = response.json()["agents"]
        assert len(agents) > 0
        print(f"✅ Agents loaded: {len(agents)}")
        
        # 2. Chat with appeal agent
        response = client.post("/api/chat", json={
            "agent": "appeal",
            "message": "I need to appeal my claim"
        })
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "agent" in data
        print(f"✅ Chat response received")
        
        # 3. Chat with renewal agent
        response = client.post("/api/chat", json={
            "agent": "renewal",
            "message": "Check my policy renewal status"
        })
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        print(f"✅ Chat with renewal agent works")
        
        print("✅ Chat test passed!")

    def test_full_tool_lifecycle(self):
        """Test full tool lifecycle: register -> update -> delete"""
        print("\n--- Testing Tool Lifecycle ---")
        
        # 1. Register a new tool
        tool_name = "test_lifecycle_tool"
        agent_name = "Test Agent"
        
        response = client.post("/api/admin/tools", json={
            "tool_name": tool_name,
            "agent_name": agent_name,
            "enabled": True
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        tool_id = data["data"]["id"]
        print(f"✅ Tool registered: {tool_name} (ID: {tool_id})")
        
        # 2. Get tools for agent
        response = client.get(f"/api/admin/tools/agent/{agent_name}")
        assert response.status_code == 200
        data = response.json()
        tools = data["data"]["tools"]
        found = any(t["id"] == tool_id for t in tools)
        assert found == True
        print(f"✅ Tool found in agent's list")
        
        # 3. Update tool (disable)
        response = client.put(f"/api/admin/tools/{tool_id}", json={"enabled": False})
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["enabled"] == False
        print(f"✅ Tool disabled")
        
        # 4. Delete tool
        response = client.delete(f"/api/admin/tools/{tool_id}")
        assert response.status_code == 200
        print(f"✅ Tool deleted")
        
        print("✅ Tool Lifecycle test passed!")

    def test_full_document_lifecycle(self):
        """Test full document lifecycle: add -> update -> delete"""
        print("\n--- Testing Document Lifecycle ---")
        
        # 1. Add a document
        doc_name = "Integration Test Document"
        doc_content = "This is an integration test document content."
        
        response = client.post("/api/admin/documents", json={
            "name": doc_name,
            "content": doc_content,
            "source": "integration_test",
            "active": True
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        doc_id = data["data"]["id"]
        print(f"✅ Document added: {doc_name} (ID: {doc_id})")
        
        # 2. Get documents
        response = client.get("/api/admin/documents")
        assert response.status_code == 200
        data = response.json()
        docs = data["data"]
        found = any(d["id"] == doc_id for d in docs)
        assert found == True
        print(f"✅ Document found in list")
        
        # 3. Update document (deactivate)
        response = client.put(f"/api/admin/documents/{doc_id}?active=false")
        if response.status_code == 422:
            response = client.put(
                f"/api/admin/documents/{doc_id}",
                json={"active": False}
            )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["active"] == False
        print(f"✅ Document deactivated")
        
        # 4. Delete document
        response = client.delete(f"/api/admin/documents/{doc_id}")
        assert response.status_code == 200
        print(f"✅ Document deleted")
        
        print("✅ Document Lifecycle test passed!")


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])