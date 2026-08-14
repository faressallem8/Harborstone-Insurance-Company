
"""
Interactive CLI for the Harborstone Planning Agent.
Usage:
    python -m planning_agent.cli [--goal "Your goal here"]
"""

import asyncio
import os
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from planning_agent.agent import HarborstoneAgent


async def run_single_goal(agent: HarborstoneAgent, goal: str) -> str:
    """Run the agent on a single goal and print the answer."""
    print(f"\nProcessing: {goal}")
    answer = await agent.solve(goal)
    print("\n" + "=" * 60)
    print("AGENT ANSWER")
    print("=" * 60)
    print(answer)
    print()
    return answer


async def interactive_loop(agent: HarborstoneAgent):
    """Run an interactive REPL."""
    print("\n" + "=" * 60)
    print("HARBORSTONE PLANNING AGENT (Ctrl+C to exit)")
    print("=" * 60)
    print("Type your insurance‑related goal and press Enter.")
    print("Examples:")
    print("  - Retrieve policy details for policy 1001 and summarize coverage.")
    print("  - Investigate claim 205 and summarize findings.")
    print("  - Assess risk for policy 305.")
    print("=" * 60)

    while True:
        try:
            goal = input("\nYour goal > ").strip()
            if not goal:
                continue
            if goal.lower() in ("exit", "quit", "q"):
                break
            await run_single_goal(agent, goal)
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Harborstone Planning Agent CLI")
    parser.add_argument("--goal", help="Run a single goal and exit", default=None)
    parser.add_argument("--dynamic", action="store_true", help="Use dynamic decomposition")
    args = parser.parse_args()

    # Load environment
    load_dotenv(project_root / ".env")
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        print("GROQ_API_KEY not set in .env")
        sys.exit(1)

    # Initialize LLM
    llm = ChatGroq(
        api_key=groq_api_key,
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    )

    # Start MCP server
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=str(project_root),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            print("Initializing MCP...")
            await session.initialize()
            print("MCP ready")

            agent = HarborstoneAgent(session, llm)

            if args.goal:
                await run_single_goal(agent, args.goal)
            else:
                await interactive_loop(agent)


if __name__ == "__main__":
    asyncio.run(main())