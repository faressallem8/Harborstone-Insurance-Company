"""
Test the orchestrator with the MCP server.
"""

import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
llm = Groq(api_key=GROQ_API_KEY)

from planning_agent.orchestrator import PlanningOrchestrator


async def test():
    print("=" * 70)
    print("🧪 TESTING PLANNING ORCHESTRATOR")
    print("=" * 70)

    server_path = Path(__file__).resolve().parent.parent / "mcp_server" / "server.py"
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Login
            await session.call_tool("login", arguments={"username": "planner", "password": "planner"})
            print("✅ Login successful")

            orchestrator = PlanningOrchestrator(session, llm)

            # Test 1: Simple lookup (Plan-and-Solve)
            print("\n" + "-" * 70)
            print("Test 1: Simple Claim Lookup → Plan-and-Solve")
            result = await orchestrator.route_sub_task({
                "type": "fetch_claim",
                "params": {"claim_id": 1}
            })
            print(f"Algorithm: {result['algorithm']}")
            print(f"Result: {result['result'][:200]}...")
            print(f"Latency: {result['latency']:.2f}s")

            # Test 2: Ranking (Tree of Thoughts)
            print("\n" + "-" * 70)
            print("Test 2: Ranking → Tree of Thoughts")
            result = await orchestrator.route_sub_task({
                "type": "rank_by_urgency",
                "params": {"claim_ids": [1, 2, 3]}
            })
            print(f"Algorithm: {result['algorithm']}")
            print(f"Best score: {result['best_score']}")
            print(f"Latency: {result['latency']:.2f}s")

            # Test 3: Decision (LATS)
            print("\n" + "-" * 70)
            print("Test 3: Decision → LATS (Grounded Environment)")
            result = await orchestrator.route_sub_task({
                "type": "make_decision",
                "params": {"claim_id": 1, "decision": "approved"}
            })
            print(f"Algorithm: {result['algorithm']}")
            print(f"Success: {result['success']}")
            print(f"Latency: {result['latency']:.2f}s")

            # Print metrics
            print("\n" + "=" * 70)
            print("📊 METRICS SUMMARY")
            print("=" * 70)
            metrics = orchestrator.get_metrics()
            for algo, data in metrics.items():
                print(f"\n{algo.replace('_', ' ').title()}:")
                print(f"  Calls: {data['total_calls']}")
                print(f"  Success Rate: {data['success_rate']:.1f}%")
                print(f"  Avg Latency: {data['avg_latency']:.2f}s")
                print(f"  Avg Tokens: {data['avg_tokens']:.0f}")


if __name__ == "__main__":
    asyncio.run(test())