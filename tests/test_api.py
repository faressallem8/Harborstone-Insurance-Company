"""
Tests for the FastAPI endpoints.
Run with: pytest tests/test_api.py -v
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pytest

# Import get_connection for cleanup
from platform.database import get_connection

try:
    from fastapi.testclient import TestClient
    from platform.app import app
    client = TestClient(app)
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("⚠️ FastAPI not installed. Skipping API tests.")
except Exception as e:
    FASTAPI_AVAILABLE = False
    print(f"⚠️ Error importing app: {e}")


@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="FastAPI not available")
class TestAPI:
    """Test API endpoints"""

    def test_health_check(self):
        """Test that the API is running"""
        response = client.get("/")
        assert response.status_code == 200
        print("✅ API is running")

    def test_get_agents(self):
        """Test GET /api/agents"""
        response = client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert len(data["agents"]) > 0
        print(f"✅ {len(data['agents'])} agents returned")

    def test_get_tools(self):
        """Test GET /api/admin/tools"""
        response = client.get("/api/admin/tools")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "data" in data
        print(f"✅ {len(data['data'])} tools returned")

    def test_get_agent_tools(self):
        """Test GET /api/admin/tools/agent/{agent_name}"""
        response = client.get("/api/admin/tools/agent/Appeal%20Agent")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["agent"] == "Appeal Agent"
        print(f"✅ {len(data['data']['tools'])} tools for Appeal Agent")

    def test_register_tool(self):
        """Test POST /api/admin/tools"""
        response = client.post("/api/admin/tools", json={
            "tool_name": "api_test_tool",
            "agent_name": "Test Agent",
            "enabled": True
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Cleanup
        tool_id = data["data"]["id"]
        client.delete(f"/api/admin/tools/{tool_id}")
        print("✅ Tool registered")

    def test_get_documents(self):
        """Test GET /api/admin/documents"""
        response = client.get("/api/admin/documents")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        print(f"✅ {len(data['data'])} documents returned")

    def test_add_document(self):
        """Test POST /api/admin/documents"""
        response = client.post("/api/admin/documents", json={
            "name": "API Test Document",
            "content": "This is an API test document.",
            "source": "api_test",
            "active": True
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Cleanup
        doc_id = data["data"]["id"]
        client.delete(f"/api/admin/documents/{doc_id}")
        print("✅ Document added")

    def test_get_hitl_tasks(self):
        """Test GET /api/admin/hitl"""
        response = client.get("/api/admin/hitl")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        print(f"✅ {len(data['data']['tasks'])} HITL tasks")

    def test_create_hitl_task(self):
        """Test POST /api/hitl"""
        response = client.post("/api/hitl", json={
            "graph_name": "api_test_graph",
            "run_id": "api_test_run",
            "node_name": "test_node",
            "state": {"test": "data"},
            "priority": "high"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Cleanup
        task_id = data["data"]["id"]
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PlatformHITLTasks WHERE id = ?", (task_id,))
            conn.commit()
        
        print("✅ HITL task created")

    def test_get_tickets(self):
        """Test GET /api/admin/tickets"""
        response = client.get("/api/admin/tickets")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        print(f"✅ {len(data['data']['tickets'])} tickets")

    def test_create_ticket(self):
        """Test POST /api/tickets"""
        response = client.post("/api/tickets", json={
            "graph_name": "api_test_graph",
            "run_id": "api_test_run",
            "node_name": "test_node",
            "state": {"test": "data"},
            "error_message": "Test error message",
            "severity": "high"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Cleanup
        ticket_id = data["data"]["id"]
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM PlatformTickets WHERE id = ?", (ticket_id,))
            conn.commit()
        
        print("✅ Ticket created")

    def test_chat_endpoint(self):
        """Test POST /api/chat"""
        response = client.post("/api/chat", json={
            "agent": "appeal",
            "message": "Hello, I need help with my claim"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "agent" in data
        print("✅ Chat endpoint works")


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])