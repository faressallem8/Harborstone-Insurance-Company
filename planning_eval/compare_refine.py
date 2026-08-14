from planning_lab.algorithms.self_refine import reflect_and_refine
from planning_agent.self_refine_wrapper import HarborstoneSelfRefine


class SelfRefineComparator:

    def __init__(self, llm, environment):
        self.llm = llm
        self.environment = environment
        self.grounded = HarborstoneSelfRefine(llm, environment)

    async def compare(self, goal: str, draft: str):

        ungrounded = reflect_and_refine(
            goal=goal,
            draft=draft,
            llm=self.llm,
        )

        grounded = await self.grounded.refine(
            goal=goal,
            draft=draft,
        )

        return {
            "goal": goal,

            "ungrounded": {
                "draft": ungrounded.draft,
                "critique": ungrounded.critique,
                "revised": ungrounded.revised,
                "grounded_issues": ungrounded.grounded_issues,
            },

            "grounded": {
                "draft": grounded.draft,
                "critique": grounded.critique,
                "revised": grounded.revised,
                "grounded_issues": grounded.grounded_issues,
            },
        }