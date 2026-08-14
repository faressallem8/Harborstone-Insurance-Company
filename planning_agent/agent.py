
from mcp import ClientSession
from langchain_core.language_models.chat_models import BaseChatModel

from planning_agent.orchestrator import PlanningOrchestrator
from planning_agent.decomposition_wrapper import HarborstoneDecomposer


class HarborstoneAgent:
    """
    Meta‑orchestrator that decomposes a goal and routes sub‑tasks to the best algorithms.
    Uses decomposition‑first to generate a full plan and execute it.
    """

    def __init__(self, session: ClientSession, llm: BaseChatModel):
        self.session = session
        self.llm = llm
        self.orchestrator = PlanningOrchestrator(session, llm)
        self.decomposer = HarborstoneDecomposer(session, llm)

    async def solve(self, goal: str, use_dynamic: bool = False) -> str:
        """
        Process a user goal and return a final answer.

        Args:
            goal: The user's natural‑language request.
            use_dynamic: If True, use dynamic decomposition instead of decomposition‑first.

        Returns:
            A string containing the final answer.
        """
        if use_dynamic:
            result = await self.decomposer.dynamic_decomposition(goal)
        else:
            result = await self.decomposer.decomposition_first(goal)

        if not result.get("success"):
            # Fallback: try Plan‑and‑Solve directly
            fallback_result = await self.orchestrator._run_plan_and_solve(goal)
            return fallback_result["result"]

        final = result.get("final", "")
        if not final.strip():
            # If final is empty, try to build a summary from outputs
            outputs = result.get("outputs", {})
            if outputs:
                lines = [f"{task}: {out}" for task, out in outputs.items()]
                return "\n".join(lines)
            return "The goal could not be completed."

        return final