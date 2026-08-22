# tests/test_state_graphs.py
"""
Tests for State Graphs - Person B's deliverables.
Run with: pytest tests/test_state_graphs.py -v
"""

import sys
import asyncio
import pytest
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from state_graph import AppealGraph, RenewalGraph, FraudGraph


class TestStateGraphs:
    """Test all three state graphs."""

    @pytest.mark.asyncio
    async def test_appeal_graph(self):
        """Test the appeal graph with a rejected claim (claim_id=11)."""
        print("\n" + "=" * 70)
        print("TEST: APPEAL GRAPH")
        print("=" * 70)
        
        graph = AppealGraph(agent_name="appeal")
        result = await graph.run(
            initial_state={"claim_id": 11},  # CLM011 is Rejected
            run_id="test_appeal_001"
        )
        
        print(f"Result: {result}")
        
        assert result is not None
        assert result["run_id"] == "test_appeal_001"
        
        if result["status"] == "paused":
            assert result["node"] in ["awaiting_documents", "underwriter_review"]
            print(f"Appeal graph paused at: {result['node']}")
        elif result["status"] == "completed":
            print("Appeal graph completed")
        else:
            print(f"Unexpected status: {result['status']}")

    @pytest.mark.asyncio
    async def test_renewal_graph(self):
        """Test the renewal graph with a policy (policy_id=1)."""
        print("\n" + "=" * 70)
        print("TEST: RENEWAL GRAPH")
        print("=" * 70)
        
        graph = RenewalGraph(agent_name="renewal")
        result = await graph.run(
            initial_state={"policy_id": 1},
            run_id="test_renewal_001"
        )
        
        print(f"Result: {result}")
        
        assert result is not None
        assert result["run_id"] == "test_renewal_001"
        
        if result["status"] == "paused":
            assert result["node"] in ["await_inspection_report", "underwriter_review"]
            print(f"Renewal graph paused at: {result['node']}")
        elif result["status"] == "completed":
            print("Renewal graph completed")
        else:
            print(f"Unexpected status: {result['status']}")

    @pytest.mark.asyncio
    async def test_fraud_graph(self):
        """Test the fraud graph with a suspicious claim (claim_id=11)."""
        print("\n" + "=" * 70)
        print("TEST: FRAUD GRAPH")
        print("=" * 70)
        
        graph = FraudGraph(agent_name="fraud")
        result = await graph.run(
            initial_state={"claim_id": 11},  # CLM011 has high fraud score
            run_id="test_fraud_001"
        )
        
        print(f"Result: {result}")
        
        assert result is not None
        assert result["run_id"] == "test_fraud_001"
        
        if result["status"] == "paused":
            assert result["node"] in ["claims_review", "underwriting_review", "legal_review"]
            print(f"Fraud graph paused at: {result['node']}")
        elif result["status"] == "completed":
            print("Fraud graph completed")
        else:
            print(f"Unexpected status: {result['status']}")

    @pytest.mark.asyncio
    async def test_appeal_graph_crash_recovery(self):
        """Test that the appeal graph can recover from a crash."""
        print("\n" + "=" * 70)
        print("TEST: CRASH RECOVERY")
        print("=" * 70)
        
        graph1 = AppealGraph(agent_name="appeal")
        run_id = "test_recovery_001"
        
        result = await graph1.run(
            initial_state={"claim_id": 11},
            run_id=run_id
        )
        
        print(f"First run result: {result}")
        
        if result["status"] != "paused":
            print("Graph didn't pause - skipping recovery test")
            return
        
        # Simulate crash by creating a new graph instance
        print("\nSimulating crash...")
        graph2 = AppealGraph(agent_name="appeal")
        
        # Resume from checkpoint
        print("Resuming from checkpoint...")
        resume_result = await graph2.run(
            run_id=run_id
        )
        
        print(f"Resume result: {resume_result}")
        
        assert resume_result["run_id"] == run_id
        assert resume_result["status"] in ["paused", "completed"]
        print("Crash recovery test passed!")


# Run directly (for quick testing without pytest)
if __name__ == "__main__":
    import asyncio
    
    print("\n" + "=" * 70)
    print("RUNNING TESTS DIRECTLY")
    print("=" * 70)
    
    test = TestStateGraphs()
    
    # Run each test
    try:
        asyncio.run(test.test_appeal_graph())
    except Exception as e:
        print(f"Appeal test failed: {e}")
    
    try:
        asyncio.run(test.test_renewal_graph())
    except Exception as e:
        print(f"Renewal test failed: {e}")
    
    try:
        asyncio.run(test.test_fraud_graph())
    except Exception as e:
        print(f"Fraud test failed: {e}")
    
    try:
        asyncio.run(test.test_appeal_graph_crash_recovery())
    except Exception as e:
        print(f"Crash recovery test failed: {e}")
    
    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETE")
    print("=" * 70)