"""
Wrapper to isolate MCP integration from the toolkit.
"""

import json
import time
from typing import Dict, Any

from planning_lab.algorithms.decomposition import decompose_goal, execute_plan, final_output
from planning_lab.algorithms.dynamic_decomposition import dynamic_decomposition, has_divergence


class HarborstoneDecomposer:
    """Wrapper for decomposition algorithms with Harborstone MCP integration."""

    def __init__(self, mcp_session, llm):
        self.mcp_session = mcp_session
        self.llm = llm
        self.traces = []

    async def decomposition_first(self, goal: str) -> Dict[str, Any]:
        """Decomposition-first: generate plan upfront, then execute."""
        start = time.time()

        try:
            # 1. Generate plan
            plan = decompose_goal(goal, self.llm)

            # 2. Execute plan with MCP
            outputs = await execute_plan(
                plan=plan,
                llm=self.llm,
                mcp_session=self.mcp_session
            )

            # 3. Get final output
            final = final_output(plan, outputs)

            success = True
            error = None

        except Exception as e:
            success = False
            error = str(e)
            final = f"ERROR: {error}"
            outputs = {}
            plan = None

        trace = {
            "method": "decomposition_first",
            "goal": goal,
            "plan": plan.model_dump() if plan else None,
            "outputs": outputs,
            "final": final,
            "acyclic": plan.is_acyclic() if plan else False,
            "nodes": len(plan.tasks) if plan else 0,
            "success": success,
            "error": error,
            "latency": time.time() - start,
            "timestamp": time.time()
        }
        self.traces.append(trace)

        return trace

    async def dynamic_decomposition(self, goal: str) -> Dict[str, Any]:
        """Dynamic decomposition: interleaved planning and execution."""
        start = time.time()

        try:
            history = await dynamic_decomposition(
                goal=goal,
                llm=self.llm,
                mcp_session=self.mcp_session,
                max_steps=5
            )

            # Detect divergence
            diverged = has_divergence(history)

            # Build final output
            final = "\n".join(f"{task}: {result}" for task, result, _ in history)

            success = True
            error = None

        except Exception as e:
            success = False
            error = str(e)
            history = []
            diverged = False
            final = f"ERROR: {error}"

        trace = {
            "method": "dynamic_decomposition",
            "goal": goal,
            "history": history,
            "final": final,
            "diverged": diverged,
            "steps": len(history),
            "success": success,
            "error": error,
            "latency": time.time() - start,
            "timestamp": time.time()
        }
        self.traces.append(trace)

        return trace

    async def compare_methods(self, goal: str) -> Dict[str, Any]:
        """Compare both methods on the same goal."""
        first = await self.decomposition_first(goal)
        dynamic = await self.dynamic_decomposition(goal)

        return {
            "goal": goal,
            "decomposition_first": {
                "nodes": first["nodes"],
                "acyclic": first["acyclic"],
                "final": first["final"],
                "latency": first["latency"],
                "success": first["success"],
                "error": first.get("error")
            },
            "dynamic": {
                "steps": dynamic["steps"],
                "diverged": dynamic["diverged"],
                "final": dynamic["final"],
                "latency": dynamic["latency"],
                "success": dynamic["success"],
                "error": dynamic.get("error")
            },
            "divergence_occurred": dynamic["diverged"],
            "context_size_comparison": "dynamic_larger" if dynamic["steps"] > first["nodes"] else "similar"
        }

    def save_traces(self, path: str = "planning_lab/artifacts/") -> str:
        """Save traces to artifacts folder."""
        import os
        os.makedirs(path, exist_ok=True)

        for i, trace in enumerate(self.traces):
            filename = f"{path}{trace['method']}_{i}.json"
            with open(filename, 'w') as f:
                json.dump(trace, f, indent=2, default=str)

        return f"Saved {len(self.traces)} traces to {path}"

    def get_traces(self) -> list:
        """Get all traces."""
        return self.traces