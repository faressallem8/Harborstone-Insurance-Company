from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field

from ..models import Thought


class ThoughtCandidates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[str] = Field(min_length=1, max_length=3, description="List of candidate next steps as strings.")


class ThoughtEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=1.0)
    rationale: str


def tree_of_thoughts(
    problem: str,
    llm: BaseChatModel,
    depth: int = 2,
    beam_width: int = 2,
) -> list[Thought]:
    frontier = [Thought(state="Start", score=0.5, rationale="root")]
    for _ in range(depth):
        candidates: list[Thought] = []
        for parent in frontier:
            generated = llm.with_structured_output(
                ThoughtCandidates,
                method="json_mode",
            ).invoke([
                ("system", """Generate candidate next steps for Tree-of-Thoughts search. 
Return a JSON object with a 'candidates' field that is an array of strings. 
Each string is a complete description of a next step. 
Do not include any other fields or nested objects.
Example: {"candidates": ["Step 1 description", "Step 2 description"]}"""),
                ("human", f"""Problem: {problem}
Partial path: {parent.state}
Propose exactly two distinct promising continuations as strings."""),
            ], temperature=0.5)
            for state in generated.candidates[:2]:
                judged = llm.with_structured_output(
                    ThoughtEvaluation,
                    method="json_mode",
                ).invoke([
                    ("system", "Evaluate a partial solution. Return a JSON with 'score' (float 0-1) and 'rationale' (string)."),
                    ("human", f"""Problem: {problem}
Candidate path: {state}
Score correctness, feasibility, and progress. Do not reward confident wording."""),
                ], temperature=0.1)
                candidates.append(
                    Thought(state=state, score=judged.score, rationale=judged.rationale)
                )
        frontier = sorted(candidates, key=lambda item: item.score, reverse=True)[:beam_width]
        if not frontier:
            break
    return frontier