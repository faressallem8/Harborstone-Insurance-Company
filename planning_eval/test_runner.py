import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from planning_eval.run_evaluation import run_planning_evaluation


# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SERVER_FILE = (
    PROJECT_ROOT
    / "mcp_server"
    / "server.py"
)

load_dotenv(PROJECT_ROOT / ".env")


# ============================================================
# LLM
# ============================================================

llm = ChatGroq(
    api_key=os.getenv("GROQ_API_KEY"),
    model=os.getenv(
        "GROQ_MODEL"
    ),
)


# ============================================================
# Runner
# ============================================================

async def main():

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "mcp_server.server",
        ],
        cwd=str(PROJECT_ROOT),
    )

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            print("Initializing MCP...")

            await session.initialize()

            print("Running planning evaluation...\n")

            result = await run_planning_evaluation(
                session=session,
                llm=llm,
            )

            print("=" * 60)
            print("Evaluation Finished")
            print("=" * 60)

            print(result)


if __name__ == "__main__":
    asyncio.run(main())