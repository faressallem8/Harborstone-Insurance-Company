# planning_agent/orchestrator.py
"""
Routes sub-tasks to PS, ToT, or LATS based on task characteristics.
"""

import time
from typing import Dict, Any
from groq import Groq
from mcp import ClientSession


from planning_lab.algorithms import plan_and_solve
from planning_lab.algorithms.tree_of_thoughts import tree_of_thoughts
from planning_lab.algorithms.lats import lats



from planning_agent.environment import HarborstoneEnvironment
from planning_agent.prompt_builder import (
    build_plan_and_solve_prompt,
    build_tree_of_thoughts_problem,
    build_lats_task,

)


class PlanningOrchestrator:
    """
    Routes each sub-task to the best planning algorithm:
    - Plan-and-Solve: Simple deterministic lookups
    - Tree of Thoughts: Tasks with multiple valid alternatives
    - LATS: Complex decisions needing external feedback
    """

    def __init__(self, session: ClientSession, llm: Groq):
        self.session = session
        self.llm = llm
        self.env = HarborstoneEnvironment(session)

        # Metrics tracking
        self.metrics = {
            "plan_and_solve": {"calls": 0, "tokens": 0, "latency": 0, "success": 0, "total": 0},
            "tree_of_thoughts": {"calls": 0, "tokens": 0, "latency": 0, "success": 0, "total": 0},
            "lats": {"calls": 0, "tokens": 0, "latency": 0, "success": 0, "total": 0},
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

        # Default: Plan-and-Solve
        else:
            return await self._run_plan_and_solve(sub_task)

    # ============================================================
    # PLAN-AND-SOLVE
    # ============================================================

    async def _run_plan_and_solve(self, sub_task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Plan-and-Solve: One plan, execute step-by-step.
        Uses the toolkit's plan_and_solve function directly.
        """
        start = time.time()

        # Build the prompt
        prompt = build_plan_and_solve_prompt(sub_task)

        # Call the toolkit's function - NO REWRITING!
        result = plan_and_solve(
            question=prompt,
            llm=self.llm
        )

        latency = time.time() - start
        tokens = len(prompt.split()) + len(result.split())

        # Track metrics
        self.metrics["plan_and_solve"]["calls"] += 1
        self.metrics["plan_and_solve"]["tokens"] += tokens
        self.metrics["plan_and_solve"]["latency"] += latency
        self.metrics["plan_and_solve"]["total"] += 1
        self.metrics["plan_and_solve"]["success"] += 1

        return {
            "algorithm": "plan_and_solve",
            "result": result,
            "latency": latency,
            "tokens": tokens,
            "sub_task": sub_task
        }

    # ============================================================
    # TREE OF THOUGHTS
    # ============================================================

    async def _run_tree_of_thoughts(self, sub_task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tree of Thoughts: Generate multiple candidates, self-evaluate.
        Uses the toolkit's tree_of_thoughts function directly.
        """
        start = time.time()

        # Build the problem description
        problem = build_tree_of_thoughts_problem(sub_task)

        # Call the toolkit's function - NO REWRITING!
        thoughts = tree_of_thoughts(
            problem=problem,
            llm=self.llm,
            depth=3,
            beam_width=5
        )

        # Evaluate the best thought against the environment
        best_thought = None
        best_score = -1

        for thought in thoughts:
            if thought.score > best_score:
                best_score = thought.score
                best_thought = thought

        latency = time.time() - start
        tokens = len(problem.split()) + sum(len(t.state.split()) for t in thoughts)

        # Track metrics
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
            "sub_task": sub_task
        }

    # ============================================================
    # LATS (MCTS with Grounded Environment)
    # ============================================================

    async def _run_lats(self, sub_task: Dict[str, Any]) -> Dict[str, Any]:
        """
        LATS: MCTS with grounded external feedback.
        Uses the toolkit's lats function with your REAL environment.
        """
        start = time.time()

        # Build the task description
        task = build_lats_task(sub_task)

        # Call the toolkit's function with your REAL environment - NO REWRITING!
        result = lats(
            task=task,
            llm=self.llm,
            environment=self.env,  # YOUR REAL ENVIRONMENT!
            iterations=10,
            n_actions=3,
            exploration_weight=1.414
        )

        latency = time.time() - start

        # Estimate tokens
        tokens = len(task.split()) + len(result.output.split())

        # Track metrics
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
            "sub_task": sub_task
        }

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
                    "success_rate": data["success"] / data["total"] * 100,
                    "avg_latency": data["latency"] / data["total"],
                    "avg_tokens": data["tokens"] / data["total"],
                }
            else:
                summary[algo] = {
                    "total_calls": 0,
                    "success_count": 0,
                    "success_rate": 0,
                    "avg_latency": 0,
                    "avg_tokens": 0,
                }
        return summary

    def reset_metrics(self):
        """Reset all metrics."""
        for algo in self.metrics:
            self.metrics[algo] = {"calls": 0, "tokens": 0, "latency": 0, "success": 0, "total": 0}