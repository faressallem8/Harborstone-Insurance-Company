"""
Tests for the MCP Server.
Run with: pytest tests/test_mcp.py -v
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pytest
import asyncio
import os
from unittest.mock import MagicMock

# Set environment variable to prevent server from running
os.environ["PYTEST_RUNNING"] = "1"

try:
    from mcp_server.server import (
        tool_registry,
        list_tools,
        call_tool,
        get_agent_tools,
        TOOL_HANDLERS,
    )
    MCP_AVAILABLE = True
except ImportError as e:
    MCP_AVAILABLE = False
    print(f"⚠️ Error importing MCP server: {e}")
except Exception as e:
    MCP_AVAILABLE = False
    print(f"⚠️ Error: {e}")


@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP server not available")
class TestMCPRegistry:
    """Test that the dynamic MCP tool registry works correctly."""

    def test_registry_initialization(self):
        """Test that the registry loads tools."""
        async def test():
            await tool_registry.initialize()

            assert tool_registry._initialized is True
            assert len(tool_registry.tools_cache) > 0

            print(
                f"✅ Registry has "
                f"{len(tool_registry.tools_cache)} agents"
            )

        asyncio.run(test())

    def test_get_tools_for_agent(self):
        """Test getting tools for an agent."""
        async def test():
            await tool_registry.initialize()

            tools = tool_registry.get_tools_for_agent("Appeal Agent")

            assert isinstance(tools, list)
            assert len(tools) > 0

            print(
                f"✅ Appeal Agent has "
                f"{len(tools)} tools: {tools}"
            )

        asyncio.run(test())

    def test_is_tool_enabled(self):
        """Test checking if a tool is enabled."""
        async def test():
            await tool_registry.initialize()

            enabled = tool_registry.is_tool_enabled(
                "Appeal Agent",
                "check_claim_status"
            )

            assert enabled is True

            print(
                "✅ check_claim_status enabled for Appeal Agent"
            )

        asyncio.run(test())

    def test_refresh_tools(self):
        """Test refreshing tools from database."""
        async def test():
            await tool_registry.initialize()
            await tool_registry.refresh()

            assert len(tool_registry.tools_cache) > 0

            print("✅ Tools refreshed")

        asyncio.run(test())


@pytest.mark.skipif(not MCP_AVAILABLE, reason="MCP server not available")
class TestMCPFunctions:
    """Test MCP helper functions."""

    def test_list_tools(self):
        """Test list_tools function."""
        async def test():
            tools = await list_tools("Appeal Agent")

            assert isinstance(tools, list)
            assert len(tools) > 0

            print(
                f"✅ list_tools returned "
                f"{len(tools)} items"
            )

        asyncio.run(test())

    def test_call_tool(self):
        """Test call_tool function with real Context."""
        async def test():
            # Create a mock context
            mock_ctx = MagicMock()
            mock_ctx.session_id = "test_session_123"

            # Test with a valid tool
            result = await call_tool(
                "Appeal Agent",
                "check_claim_status",
                {"claim_id": 1},
                mock_ctx
            )

            assert result is not None
            assert result["status"] == "success"

            print(
                f"✅ call_tool returned: {result}"
            )

        asyncio.run(test())

    def test_call_tool_disabled(self):
        """Test that call_tool fails when tool is disabled."""
        async def test():
            from web_platform.database import (
                register_tool,
                delete_tool,
                update_tool,
                get_tool_by_name_and_agent,
            )

            agent_name = "Test Disabled Agent"
            tool_name = "test_disabled_tool"

            # Clean up any existing tool
            existing = get_tool_by_name_and_agent(
                tool_name,
                agent_name
            )

            if existing:
                delete_tool(existing["id"])
                await tool_registry.refresh()

            # Create a mock handler
            async def mock_handler(test: str) -> dict:
                return {
                    "status": "success",
                    "data": "test"
                }

            # Add handler temporarily
            TOOL_HANDLERS[tool_name] = mock_handler

            # Register tool as disabled
            tool = register_tool(
                tool_name,
                agent_name,
                enabled=False
            )

            await tool_registry.refresh()

            # Verify tool is disabled
            enabled = tool_registry.is_tool_enabled(
                agent_name,
                tool_name
            )

            assert enabled is False

            # Try to call disabled tool
            mock_ctx = MagicMock()
            mock_ctx.session_id = "test_session"

            result = await call_tool(
                agent_name,
                tool_name,
                {"test": "data"},
                mock_ctx
            )

            assert result["status"] == "error"
            assert "not enabled" in result["error"]

            print(
                "✅ Disabled tool correctly rejected: "
                f"{result['error']}"
            )

            # Cleanup
            delete_tool(tool["id"])

            if tool_name in TOOL_HANDLERS:
                del TOOL_HANDLERS[tool_name]

            await tool_registry.refresh()

        asyncio.run(test())

        print(
            "✅ test_call_tool_disabled passed!"
        )

    def test_dynamic_tool_registry_flow(self):
        """
        Test full dynamic registry flow:

        register
            ↓
        enabled
            ↓
        call works
            ↓
        disable
            ↓
        call fails
            ↓
        enable
            ↓
        call works again
            ↓
        cleanup
        """
        print("\n--- Testing Dynamic Registry Flow ---")

        async def test():
            from web_platform.database import (
                register_tool,
                delete_tool,
                update_tool,
                get_tool_by_name_and_agent,
            )

            import mcp_server.server as mcp_module

            agent_name = "Test Flow Agent"
            tool_name = "test_flow_tool"

            # -------------------------------------------------
            # 0. Clean up any existing test tool
            # -------------------------------------------------

            existing = get_tool_by_name_and_agent(
                tool_name,
                agent_name
            )

            if existing:
                delete_tool(existing["id"])
                await tool_registry.refresh()

                print(
                    f"🧹 Cleaned up existing tool: "
                    f"{tool_name}"
                )

            # -------------------------------------------------
            # 1. Create mock handler
            # -------------------------------------------------

            async def mock_handler(test: str) -> dict:
                return {
                    "status": "success",
                    "data": "flow_test_data"
                }

            # Add handler directly to the actual
            # mcp_server.server module
            mcp_module.TOOL_HANDLERS[tool_name] = mock_handler

            # -------------------------------------------------
            # 2. Register tool as enabled
            # -------------------------------------------------

            tool = register_tool(
                tool_name,
                agent_name,
                enabled=True
            )

            await tool_registry.refresh()

            print(
                f"✅ Tool registered: "
                f"{tool_name} for {agent_name}"
            )

            # -------------------------------------------------
            # 3. Verify tool is enabled
            # -------------------------------------------------

            enabled = tool_registry.is_tool_enabled(
                agent_name,
                tool_name
            )

            assert enabled is True

            print(
                f"✅ Tool is enabled: {enabled}"
            )

            # -------------------------------------------------
            # 4. Call enabled tool
            # -------------------------------------------------

            mock_ctx = MagicMock()
            mock_ctx.session_id = "test_session"

            result = await call_tool(
                agent_name,
                tool_name,
                {"test": "data"},
                mock_ctx
            )

            assert result["status"] == "success"
            assert result["result"]["status"] == "success"
            assert (
                result["result"]["data"]
                == "flow_test_data"
            )

            print(
                "✅ Tool called successfully"
            )

            # -------------------------------------------------
            # 5. Disable tool
            # -------------------------------------------------

            update_tool(
                tool["id"],
                enabled=False
            )

            await tool_registry.refresh()

            print("✅ Tool disabled")

            # -------------------------------------------------
            # 6. Verify tool is disabled
            # -------------------------------------------------

            enabled = tool_registry.is_tool_enabled(
                agent_name,
                tool_name
            )

            assert enabled is False

            print(
                f"✅ Tool is now disabled: {enabled}"
            )

            # -------------------------------------------------
            # 7. Calling disabled tool must fail
            # -------------------------------------------------

            result = await call_tool(
                agent_name,
                tool_name,
                {"test": "data"},
                mock_ctx
            )

            assert result["status"] == "error"
            assert "not enabled" in result["error"]

            print(
                "✅ Tool call failed as expected: "
                f"{result['error']}"
            )

            # -------------------------------------------------
            # 8. Re-enable tool
            # -------------------------------------------------

            update_tool(
                tool["id"],
                enabled=True
            )

            await tool_registry.refresh()

            print("✅ Tool re-enabled")

            # -------------------------------------------------
            # 9. Call enabled tool again
            # -------------------------------------------------

            result = await call_tool(
                agent_name,
                tool_name,
                {"test": "data"},
                mock_ctx
            )

            assert result["status"] == "success"
            assert result["result"]["status"] == "success"
            assert (
                result["result"]["data"]
                == "flow_test_data"
            )

            print(
                "✅ Tool works again"
            )

            # -------------------------------------------------
            # 10. Cleanup
            # -------------------------------------------------

            delete_tool(tool["id"])

            if tool_name in mcp_module.TOOL_HANDLERS:
                del mcp_module.TOOL_HANDLERS[tool_name]

            await tool_registry.refresh()

            print(
                "✅ Cleanup complete"
            )

        asyncio.run(test())

        print(
            "✅ Dynamic Registry Flow test passed!"
        )


# Run all tests
if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--tb=short"
        ]
    )