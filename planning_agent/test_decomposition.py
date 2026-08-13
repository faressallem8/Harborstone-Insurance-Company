"""
Tests for decomposition - DAG, cycles, MCP, divergence.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from planning_lab.models import Plan, Task, ALLOWED_TOOLS
from planning_lab.algorithms.decomposition import execute_plan, decompose_goal
from planning_agent.decomposition_wrapper import HarborstoneDecomposer


class TestDecomposition:

    # ============================================================
    # DAG TESTS (6 tests)
    # ============================================================

    def test_dag_valid(self):
        """Test that a valid DAG is accepted."""
        plan = Plan(
            goal="Test goal with valid length",
            tasks=[
                Task(id="t1", instruction="First task", depends_on=[]),
                Task(id="t2", instruction="Second task", depends_on=["t1"]),
                Task(id="t3", instruction="Third task", depends_on=["t2"]),
            ]
        )
        assert plan.is_acyclic() is True
        assert len(plan.tasks) == 3

    def test_duplicate_ids(self):
        """Test that duplicate task IDs are rejected."""
        with pytest.raises(ValueError, match="Duplicate task IDs"):
            Plan(
                goal="Test goal with valid length",
                tasks=[
                    Task(id="t1", instruction="First task"),
                    Task(id="t1", instruction="Duplicate task"),
                ]
            )

    def test_missing_dependency(self):
        """Test that missing dependencies are rejected."""
        with pytest.raises(ValueError, match="depends on missing"):
            Plan(
                goal="Test goal with valid length",
                tasks=[
                    Task(id="t1", instruction="First task", depends_on=["missing"]),
                ]
            )

    def test_self_dependency(self):
        """Test that self-dependencies are rejected."""
        with pytest.raises(ValueError, match="depends on itself"):
            Plan(
                goal="Test goal with valid length",
                tasks=[
                    Task(id="t1", instruction="First task", depends_on=["t1"]),
                ]
            )

    def test_cycle_detection(self):
        """Test that cycles are rejected."""
        with pytest.raises(ValueError, match="Cycle detected"):
            Plan(
                goal="Test goal with valid length",
                tasks=[
                    Task(id="t1", instruction="Task 1", depends_on=["t3"]),
                    Task(id="t2", instruction="Task 2", depends_on=["t1"]),
                    Task(id="t3", instruction="Task 3", depends_on=["t2"]),
                ]
            )

    def test_exactly_one_synthesis(self):
        """Test that plans with multiple terminal tasks are rejected."""
        with pytest.raises(ValueError, match="exactly one terminal"):
            Plan(
                goal="Test goal with valid length",
                tasks=[
                    Task(id="t1", instruction="Task 1"),
                    Task(id="t2", instruction="Task 2"),
                ]
            )

    # ============================================================
    # MCP TOOL TESTS (4 tests)
    # ============================================================

    def test_task_with_mcp_tool(self):
        """Test that Task can have MCP tool and params."""
        task = Task(
            id="check_claim",
            instruction="Check claim 4",
            tool="check_claim_status",
            params={"claim_id": 4}
        )
        assert task.tool == "check_claim_status"
        assert task.params == {"claim_id": 4}

    def test_plan_validation_with_tools(self):
        """Test that plan validates with MCP tools."""
        plan = Plan(
            goal="Test goal with valid length",
            tasks=[
                Task(id="t1", instruction="Check claim", tool="check_claim_status", params={"claim_id": 4}),
                Task(id="t2", instruction="Synthesize", depends_on=["t1"])
            ]
        )
        assert plan.is_acyclic() is True

    def test_unknown_tool_rejected_by_plan(self):
        """Test that unknown tools are rejected by Plan validation."""
        with pytest.raises(ValueError, match="unknown tool"):
            Plan(
                goal="Test goal with valid length",
                tasks=[
                    Task(id="t1", instruction="Check claim", tool="fake_tool", params={"claim_id": 4}),
                    Task(id="t2", instruction="Synthesize", depends_on=["t1"])
                ]
            )

    def test_allowed_tools_are_defined(self):
        """Test that ALLOWED_TOOLS contains expected tools."""
        expected_tools = {
            "check_claim_status",
            "get_customer_info",
            "get_policy_details",
            "file_claim",
            "assess_risk",
            "approve_claim"
        }
        assert ALLOWED_TOOLS == expected_tools

    # ============================================================
    # MCP EXECUTION TESTS (2 tests) - async
    # ============================================================

    @pytest.mark.asyncio
    async def test_mcp_execution(self):
        """Test that MCP tools are called correctly."""
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value="Claim found")

        mock_llm = MagicMock()

        plan = Plan(
            goal="Test goal with valid length",
            tasks=[
                Task(
                    id="t1",
                    instruction="Check claim",
                    tool="check_claim_status",
                    params={"claim_id": 4}
                )
            ]
        )

        outputs = await execute_plan(
            plan=plan,
            llm=mock_llm,
            mcp_session=mock_session
        )

        mock_session.call_tool.assert_called_once_with(
            "check_claim_status",
            {"claim_id": 4}
        )
        assert outputs["t1"] == "Claim found"

    @pytest.mark.asyncio
    async def test_mcp_execution_failure(self):
        """Test that MCP failures are captured."""
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            side_effect=Exception("Claim not found")
        )

        mock_llm = MagicMock()

        plan = Plan(
            goal="Test goal with valid length",
            tasks=[
                Task(
                    id="t1",
                    instruction="Check claim",
                    tool="check_claim_status",
                    params={"claim_id": 999}
                )
            ]
        )

        outputs = await execute_plan(
            plan=plan,
            llm=mock_llm,
            mcp_session=mock_session
        )

        assert outputs["t1"] == "ERROR: Claim not found"

    # ============================================================
    # DYNAMIC DECOMPOSITION TESTS (2 tests) - async
    # ============================================================

    @pytest.mark.asyncio
    async def test_dynamic_success(self):
        """Test that dynamic decomposition works with success."""
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value="Claim found")

        # Mock LLM decisions
        decision1 = MagicMock()
        decision1.done = False
        decision1.next_task = "Check claim"
        decision1.tool = "check_claim_status"
        decision1.params = {"claim_id": 4}

        decision2 = MagicMock()
        decision2.done = True
        decision2.next_task = ""

        mock_structured = MagicMock()
        mock_structured.invoke = MagicMock(side_effect=[decision1, decision2])

        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)
        mock_llm.invoke = MagicMock(return_value=MagicMock(content="Result"))

        from planning_lab.algorithms.dynamic_decomposition import dynamic_decomposition

        history = await dynamic_decomposition(
            goal="Test goal with valid length",
            llm=mock_llm,
            mcp_session=mock_session,
            max_steps=3
        )

        assert len(history) == 1
        assert history[0][0] == "Check claim"
        assert "Claim found" in history[0][1]

    @pytest.mark.asyncio
    async def test_dynamic_failure_with_divergence(self):
        """Test that dynamic handles MCP failures with divergence."""
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            side_effect=Exception("Claim not found")
        )

        # Decision 1: Check claim (fails)
        decision1 = MagicMock()
        decision1.done = False
        decision1.next_task = "Check claim 999"
        decision1.tool = "check_claim_status"
        decision1.params = {"claim_id": 999}

        # Alternative decision after failure (will be used in next iteration)
        decision2 = MagicMock()
        decision2.done = False
        decision2.next_task = "Try alternative"
        decision2.tool = None
        decision2.params = {}

        # Decision 3: Done
        decision3 = MagicMock()
        decision3.done = True
        decision3.next_task = ""

        mock_structured = MagicMock()
        mock_structured.invoke = MagicMock(side_effect=[decision1, decision2, decision3])

        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)
        mock_llm.invoke = MagicMock(return_value=MagicMock(content="Alternative executed"))

        from planning_lab.algorithms.dynamic_decomposition import dynamic_decomposition

        history = await dynamic_decomposition(
            goal="Test goal with valid length",
            llm=mock_llm,
            mcp_session=mock_session,
            max_steps=5
        )

        # Should have failure and divergence
        failed = [h for h in history if h[2].get("success") is False]
        assert len(failed) > 0
        assert "ERROR" in failed[0][1]
        assert any(h[2].get("diverged", False) for h in history)

    # ============================================================
    # DIVERGENCE TEST (1 test) - async - FINAL FIX
    # ============================================================

    @pytest.mark.asyncio
    async def test_decomposition_first_vs_dynamic(self):
        """Test that decomposition-first and dynamic diverge on failure."""
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            side_effect=Exception("Claim not found")
        )

        # ============================================================
        # MOCK FOR DECOMPOSITION-FIRST
        # ============================================================
        # Create a REAL Plan that passes validation
        # t1 depends on nothing (root), t4 is the only terminal
        real_plan = Plan(
            goal="Investigate claim 999",
            tasks=[
                Task(id="t1", instruction="Check claim", tool="check_claim_status", params={"claim_id": 999}),
                Task(id="t2", instruction="Get policy", tool="get_policy_details", params={"policy_id": 1}, depends_on=["t1"]),
                Task(id="t3", instruction="Assess risk", tool="assess_risk", params={"policy_id": 1}, depends_on=["t2"]),
                Task(id="t4", instruction="Make decision", depends_on=["t2", "t3"])
            ]
        )

        mock_plan = MagicMock()
        mock_plan.model_dump.return_value = real_plan.model_dump()
        mock_plan.is_acyclic.return_value = True
        mock_plan.tasks = real_plan.tasks

        def get_task(task_id):
            for t in mock_plan.tasks:
                if t.id == task_id:
                    return t
            raise KeyError(task_id)
        mock_plan.task = get_task

        def execution_batches():
            yield ["t1"]
            yield ["t2", "t3"]
            yield ["t4"]
        mock_plan.execution_batches = execution_batches
        mock_plan.terminal_tasks = lambda: ["t4"]

        mock_structured_decomp = MagicMock()
        mock_structured_decomp.invoke = MagicMock(return_value=mock_plan)

        mock_llm_decomp = MagicMock()
        mock_llm_decomp.with_structured_output = MagicMock(return_value=mock_structured_decomp)
        mock_llm_decomp.invoke = MagicMock(
            return_value=MagicMock(content="Decision made: claim approved")
        )

        # ============================================================
        # MOCK FOR DYNAMIC DECOMPOSITION
        # ============================================================
        decision1 = MagicMock()
        decision1.done = False
        decision1.next_task = "Check claim 999"
        decision1.tool = "check_claim_status"
        decision1.params = {"claim_id": 999}

        decision2 = MagicMock()
        decision2.done = False
        decision2.next_task = "Try alternative"
        decision2.tool = None
        decision2.params = {}

        decision3 = MagicMock()
        decision3.done = True
        decision3.next_task = ""

        mock_structured_dynamic = MagicMock()
        mock_structured_dynamic.invoke = MagicMock(side_effect=[decision1, decision2, decision3])

        mock_llm_dynamic = MagicMock()
        mock_llm_dynamic.with_structured_output = MagicMock(return_value=mock_structured_dynamic)
        mock_llm_dynamic.invoke = MagicMock(return_value=MagicMock(content="Alternative executed"))

        # ============================================================
        # RUN TESTS WITH SEPARATE MOCKS
        # ============================================================
        decomposer_first = HarborstoneDecomposer(mock_session, mock_llm_decomp)
        first = await decomposer_first.decomposition_first("Investigate claim 999")

        decomposer_dynamic = HarborstoneDecomposer(mock_session, mock_llm_dynamic)
        dynamic = await decomposer_dynamic.dynamic_decomposition("Investigate claim 999")

        # Verify divergence
        assert first["acyclic"] is True
        assert dynamic["diverged"] is True
        assert "ERROR" in dynamic["final"]
        assert first["final"] != dynamic["final"]

    # ============================================================
    # TRACE TEST (1 test) - async
    # ============================================================

    @pytest.mark.asyncio
    async def test_traces_are_saved(self):
        """Test that traces are saved correctly."""
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value="Result")

        decision = MagicMock()
        decision.done = True
        decision.next_task = ""

        mock_structured = MagicMock()
        mock_structured.invoke = MagicMock(return_value=decision)

        mock_llm = MagicMock()
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

        decomposer = HarborstoneDecomposer(mock_session, mock_llm)

        await decomposer.dynamic_decomposition("Test goal with valid length")

        traces = decomposer.get_traces()
        assert len(traces) == 1
        assert traces[0]["method"] == "dynamic_decomposition"
        assert traces[0]["goal"] == "Test goal with valid length"
        assert "timestamp" in traces[0]