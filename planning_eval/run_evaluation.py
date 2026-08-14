"""
Runs the complete evaluation suite for the Harborstone Planning Agent.

Every planning algorithm is executed on the same test cases in order
to produce fair comparison metrics and reusable artifacts.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from planning_eval.test_cases import TEST_CASES
from planning_eval.compare_refine import SelfRefineComparator

from planning_agent.ungrounded_environment import (
    UngroundedEnvironmentAdapter,
)

from planning_agent.environment import HarborstoneEnvironment
from planning_agent.orchestrator import PlanningOrchestrator


class EvaluationRunner:
    """
    Executes every required evaluation for the planning assignment.

    Responsibilities
    ----------------
    - Execute every planning algorithm.
    - Compare grounded vs ungrounded approaches.
    - Collect metrics.
    - Save evaluation artifacts.
    """

    def __init__(
        self,
        session,
        llm,
        artifacts_dir: str = "artifacts",
    ):
        self.session = session
        self.llm = llm

        self.orchestrator = PlanningOrchestrator(
            session=session,
            llm=llm,
        )

        self.grounded_environment = HarborstoneEnvironment(session)

        # Toolkit's default randomized environment
        self.ungrounded_environment = UngroundedEnvironmentAdapter()

        self.refine_comparator = SelfRefineComparator(
            llm=llm,
            environment=self.grounded_environment,
        )

        self.results: list[dict[str, Any]] = []

        self.artifacts_dir = artifacts_dir
        os.makedirs(self.artifacts_dir, exist_ok=True)

    def save_artifact(
        self,
        filename: str,
        data: dict,
    ) -> None:
        """
        Save a JSON artifact for later analysis.
        """

        path = os.path.join(
            self.artifacts_dir,
            filename,
        )

        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False,
                default=str,
            )

    def _extract_text(
        self,
        value: Any,
    ) -> str:
        """
        Extract plain text from toolkit outputs.
        """

        if isinstance(value, str):
            return value

        if hasattr(value, "content"):
            return str(value.content)

        if hasattr(value, "output"):
            return str(value.output)

        return str(value)

    async def run_all(self) -> list[dict[str, Any]]:
        """
        Execute every evaluation test case using all required planning methods.
        """
        for case in TEST_CASES:
            print(f"\nRunning {case.id} - {case.title}")
            case_result = {
                "id": case.id,
                "title": case.title,
                "goal": case.goal,
            }
            # -------------------------
            # Planning algorithms
            # -------------------------
            case_result["plan_and_solve"] = (
                await self.orchestrator.evaluate_goal(
                    "plan_and_solve",
                    case.goal,
                )
            )
            case_result["tree_of_thoughts"] = (
                await self.orchestrator.evaluate_goal(
                    "tree_of_thoughts",
                    case.goal,
                )
            )
            case_result["lats_grounded"] = (
                await self.orchestrator.evaluate_goal(
                    "lats",
                    case.goal,
                    environment=self.grounded_environment,
                )
            )
            case_result["lats_ungrounded"] = (
                await self.orchestrator.evaluate_goal(
                    "lats",
                    case.goal,
                    environment=self.ungrounded_environment,
                )
            )
            # -------------------------
            # Self-Refine comparison
            # -------------------------

            refine_result = self.refine_comparator.compare(
                goal=case.goal,
                draft=self._extract_text(
                    case_result["plan_and_solve"]["result"]
                )
            )

            case_result["self_refine"] = refine_result

            self.results.append(case_result)
            self.save_artifact(
                f"{case.id}.json",
                case_result,
            )
        return self.results

    def save_results(self) -> str:
        """
        Save the complete evaluation report.
        """

        output = os.path.join(
            self.artifacts_dir,
            "evaluation_results.json",
        )

        with open(output, "w", encoding="utf-8") as f:
            json.dump(
                self.results,
                f,
                indent=4,
                ensure_ascii=False,
                default=str,
            )

        return output


    def build_summary_table(self) -> list[dict]:
        """
        Build a compact comparison table for the README.
        """

        return self.orchestrator.get_metrics()


    async def evaluate(self):
        """
        Execute the full evaluation pipeline.
        """

        start = time.time()

        await self.run_all()

        report = self.save_results()

        metrics = self.build_summary_table()

        elapsed = time.time() - start

        return {
            "results_file": report,
            "summary": metrics,
            "total_cases": len(TEST_CASES),
            "elapsed_seconds": round(elapsed, 2),
        }

async def run_planning_evaluation(
    session,
    llm,
):
    """
    Entry point used by demos and notebooks.
    """

    runner = EvaluationRunner(
        session=session,
        llm=llm,
    )

    return await runner.evaluate()