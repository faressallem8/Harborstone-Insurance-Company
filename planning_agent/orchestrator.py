# planning_agent/orchestrator.py
"""
Routes sub-tasks to PS, ToT, or LATS based on task characteristics.
"""

import time
from typing import Dict, Any, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from mcp import ClientSession


from planning_lab.algorithms import plan_and_solve
from planning_lab.algorithms.tree_of_thoughts import tree_of_thoughts
from planning_lab.algorithms.lats import lats



from planning_agent.environment import HarborstoneEnvironment



# ============================================================
# NEW: Import for decomposition
# ============================================================
from planning_agent.decomposition_wrapper import HarborstoneDecomposer
# ============================================================


class PlanningOrchestrator:
    """
    Routes each sub-task to the best planning algorithm:
    - Plan-and-Solve: Simple deterministic lookups
    - Tree of Thoughts: Tasks with multiple valid alternatives
    - LATS: Complex decisions needing external feedback
    """

    def __init__(self, session: ClientSession, llm: BaseChatModel):
        self.session = session
        self.llm = llm
        self.env = HarborstoneEnvironment(session)

        # ============================================================
        # NEW: Decomposer instance
        # ============================================================
        self.decomposer = HarborstoneDecomposer(session, llm)
        # ============================================================

        # Metrics tracking
        self.metrics = {
            "plan_and_solve": {"calls": 0, "tokens": 0, "latency": 0, "success": 0, "total": 0},
            "tree_of_thoughts": {"calls": 0, "tokens": 0, "latency": 0, "success": 0, "total": 0},
            "lats": {"calls": 0, "tokens": 0, "latency": 0, "success": 0, "total": 0},
            # ============================================================
            # NEW: Decomposition metrics
            # ============================================================
            "decomposition_first": {"calls": 0, "tokens": 0, "latency": 0, "success": 0, "total": 0, "failures": 0},
            "dynamic_decomposition": {"calls": 0, "tokens": 0, "latency": 0, "success": 0, "total": 0, "failures": 0},
            # ============================================================
        }

    async def route_sub_task(self, sub_task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route a sub-task to the appropriate algorithm.

        Args:
            sub_task: {"type": "...", "params": {...}}

        Returns:
            Result from the chosen planner with metrics.
        """
        task_type = sub_task.get("type")

        # ---- Routing Rules ----
        # Plan-and-Solve: Simple deterministic lookups
        if task_type in ["fetch_claim", "fetch_policy", "fetch_customer", "fetch_vessel"]:
            return await self._run_plan_and_solve(sub_task)

        # Tree of Thoughts: Tasks with multiple valid alternatives
        elif task_type in ["rank_by_urgency", "assess_risk", "evaluate_options"]:
            return await self._run_tree_of_thoughts(sub_task)

        # LATS: Complex decisions needing external feedback
        elif task_type in ["make_decision", "investigate_fraud", "check_fraud_indicators"]:
            return await self._run_lats(sub_task)

        # ============================================================
        # NEW: Decomposition routes
        # ============================================================
        elif task_type in ["investigate_claim", "complex_investigation"]:
            goal = sub_task.get("goal", "Investigate claim")
            use_dynamic = sub_task.get("use_dynamic", False)
            if use_dynamic:
                return await self._run_dynamic_decomposition(goal)
            else:
                return await self._run_decomposition_first(goal)
        # ============================================================

        # Default: Plan-and-Solve
        else:
            return await self._run_plan_and_solve(sub_task)

    # ============================================================
    # PLAN-AND-SOLVE
    # ============================================================

    async def _run_plan_and_solve(self, goal: str) -> Dict[str, Any]:
        """Run Plan-and-Solve on the goal string."""
        start = time.time()
        result = plan_and_solve(question=goal, llm=self.llm)
        latency = time.time() - start
        tokens = len(goal.split()) + len(result.split())

        self.metrics["plan_and_solve"]["calls"] += 1
        self.metrics["plan_and_solve"]["tokens"] += tokens
        self.metrics["plan_and_solve"]["latency"] += latency
        self.metrics["plan_and_solve"]["total"] += 1
        self.metrics["plan_and_solve"]["success"] += 1

        return {
            "algorithm": "plan_and_solve",
            "success": True,
            "result": result,
            "latency": latency,
            "tokens": tokens,
        }

    # ============================================================
    # TREE OF THOUGHTS
    # ============================================================

    async def _run_tree_of_thoughts(self, goal: str) -> Dict[str, Any]:
        """Run Tree of Thoughts on the goal string."""
        start = time.time()
        thoughts = tree_of_thoughts(
            problem=goal,
            llm=self.llm,
            depth=3,
            beam_width=5
        )
        best_thought = None
        best_score = -1
        for thought in thoughts:
            if thought.score > best_score:
                best_score = thought.score
                best_thought = thought

        latency = time.time() - start
        tokens = len(goal.split()) + sum(len(t.state.split()) for t in thoughts)

        self.metrics["tree_of_thoughts"]["calls"] += 1
        self.metrics["tree_of_thoughts"]["tokens"] += tokens
        self.metrics["tree_of_thoughts"]["latency"] += latency
        self.metrics["tree_of_thoughts"]["total"] += 1
        if best_score > 0.7:
            self.metrics["tree_of_thoughts"]["success"] += 1

        return {
            "algorithm": "tree_of_thoughts",
            "best_thought": best_thought.state if best_thought else None,
            "best_score": best_score,
            "all_thoughts": [{"state": t.state, "score": t.score, "rationale": t.rationale} for t in thoughts],
            "latency": latency,
            "tokens": tokens,
        }

    # ============================================================
    # LATS (MCTS with Grounded Environment)
    # ============================================================

    async def _run_lats(self, goal: str, environment: Optional[HarborstoneEnvironment] = None) -> Dict[str, Any]:
        """Run LATS on the goal string."""
        start = time.time()
        actual_env = environment or self.env
        result = await lats(
            task=goal,
            llm=self.llm,
            environment=actual_env,
            iterations=3,
            n_actions=2,
            exploration_weight=1.414
        )
        latency = time.time() - start
        tokens = len(goal.split()) + len(result.output.split())

        self.metrics["lats"]["calls"] += 1
        self.metrics["lats"]["tokens"] += tokens
        self.metrics["lats"]["latency"] += latency
        self.metrics["lats"]["total"] += 1
        if result.success:
            self.metrics["lats"]["success"] += 1

        return {
            "algorithm": "lats",
            "success": result.success,
            "output": result.output,
            "best_score": result.best_score,
            "iterations": result.iterations,
            "latency": latency,
            "tokens": tokens,
        }

    # ============================================================
    # NEW: DECOMPOSITION-FIRST
    # ============================================================

    async def _run_decomposition_first(self, goal: str) -> Dict[str, Any]:
        """
        Decomposition-first: generate plan upfront, then execute.
        """
        import time
        start = time.time()
        result = await self.decomposer.decomposition_first(goal)
        latency = time.time() - start

        self.metrics["decomposition_first"]["calls"] += 1
        self.metrics["decomposition_first"]["total"] += 1
        self.metrics["decomposition_first"]["latency"] += latency

        if result.get("success", False):
            self.metrics["decomposition_first"]["success"] += 1
        else:
            self.metrics["decomposition_first"]["failures"] += 1

        return {
            "algorithm": "decomposition_first",
            "result": result,
            "latency": latency,
            "success": result.get("success", False)
        }

    # ============================================================
    # NEW: DYNAMIC DECOMPOSITION
    # ============================================================

    async def _run_dynamic_decomposition(self, goal: str) -> Dict[str, Any]:
        """
        Dynamic decomposition: interleaved planning and execution.
        """
        import time
        start = time.time()
        result = await self.decomposer.dynamic_decomposition(goal)
        latency = time.time() - start

        self.metrics["dynamic_decomposition"]["calls"] += 1
        self.metrics["dynamic_decomposition"]["total"] += 1
        self.metrics["dynamic_decomposition"]["latency"] += latency

        if result.get("success", False):
            self.metrics["dynamic_decomposition"]["success"] += 1
        else:
            self.metrics["dynamic_decomposition"]["failures"] += 1

        return {
            "algorithm": "dynamic_decomposition",
            "result": result,
            "latency": latency,
            "success": result.get("success", False)
        }

    async def evaluate_goal(
        self,
        algorithm: str,
        goal: str,
        environment: Optional[HarborstoneEnvironment] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a goal using the requested planning algorithm.
        Now the goal string is passed directly to the algorithm.
        """
        algorithm = algorithm.lower()

        if algorithm == "plan_and_solve":
            return await self._run_plan_and_solve(goal)

        elif algorithm == "tree_of_thoughts":
            return await self._run_tree_of_thoughts(goal)

        elif algorithm == "lats":
            return await self._run_lats(goal, environment)

        elif algorithm == "decomposition_first":
            return await self._run_decomposition_first(goal)

        elif algorithm == "dynamic_decomposition":
            return await self._run_dynamic_decomposition(goal)

        raise ValueError(f"Unknown planning algorithm: {algorithm}")
    # ============================================================
    # METRICS
    # ============================================================

    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics for all algorithms."""
        summary = {}
        for algo, data in self.metrics.items():
            if data["total"] > 0:
                summary[algo] = {
                    "total_calls": data["total"],
                    "success_count": data["success"],
                    "failure_count": data.get("failures", 0),
                    "success_rate": data["success"] / data["total"] * 100 if data["total"] > 0 else 0,
                    "avg_latency": data["latency"] / data["total"] if data["total"] > 0 else 0,
                    "avg_tokens": data["tokens"] / data["total"] if data["total"] > 0 else 0,
                }
            else:
                summary[algo] = {
                    "total_calls": 0,
                    "success_count": 0,
                    "failure_count": 0,
                    "success_rate": 0,
                    "avg_latency": 0,
                    "avg_tokens": 0,
                }
        return summary

    def reset_metrics(self):
        """Reset all metrics."""
        for algo in self.metrics:
            self.metrics[algo] = {"calls": 0, "tokens": 0, "latency": 0, "success": 0, "total": 0}