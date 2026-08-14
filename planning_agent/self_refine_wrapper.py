"""
Grounded wrapper around the toolkit Self-Refine algorithm.

The toolkit implementation is intentionally left unchanged.
This wrapper injects grounded feedback from HarborstoneEnvironment
before invoking the original Self-Refine algorithm.
"""

from planning_lab.algorithms.self_refine import (
    reflect_and_refine,
    ReflectionResult,
)

from planning_agent.environment import HarborstoneEnvironment


class HarborstoneSelfRefine:
    """
    Harborstone wrapper for the toolkit Self-Refine algorithm.

    Responsibilities
    ----------------
    1. Evaluate the draft using the real Harborstone environment.
    2. Inject grounded feedback into the refinement prompt.
    3. Delegate refinement to the original toolkit implementation.
    """

    def __init__(self, llm, environment: HarborstoneEnvironment):
        self.llm = llm
        self.environment = environment

    async def refine(
        self,
        goal: str,
        draft: str,
    ) -> ReflectionResult:
        """
        Execute grounded Self-Refine.

        Parameters
        ----------
        goal
            Original user objective.

        draft
            Initial draft produced by the planning algorithm.

        Returns
        -------
        ReflectionResult
            Original toolkit output.
        """

        feedback = await self.environment.evaluate(
            state=draft,
            goal=goal,
        )

        grounded_goal = f"""
{goal}

==================================================
Grounded Environment Validation
==================================================

Environment Success:
{feedback.success}

Environment Score:
{feedback.score:.2f}

Environment Feedback:
{feedback.feedback}

Environment Details:
{feedback.details}

Use the validation above while critiquing and revising the draft.
Do not contradict the environment.
"""

        result = reflect_and_refine(
            goal=grounded_goal,
            draft=draft,
            llm=self.llm,
        )
        
        return result