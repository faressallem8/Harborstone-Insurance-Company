import re
from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel


def deterministic_checks(goal: str, draft: str) -> list[str]:
    issues: list[str] = []
    if len(draft.split()) < 80:
        issues.append("The deliverable is under 80 words and is probably incomplete.")
    goal_terms = {
        word.lower()
        for word in re.findall(r"[A-Za-z]{5,}", goal)
        if word.lower() not in {"create", "design", "write", "build", "about", "using"}
    }
    represented = [term for term in goal_terms if term in draft.lower()]
    if goal_terms and not represented:
        issues.append("The output contains none of the goal's significant terms.")
    if not re.search(r"(^|\n)(#{1,3}\s+|\d+[.)]\s+|[-*]\s+)", draft):
        issues.append("The deliverable has no visible structure (headings or list items).")
    return issues


@dataclass
class ReflectionResult:
    draft: str
    critique: str
    revised: str
    grounded_issues: list[str]


def reflect_and_refine(goal: str, draft: str, llm: BaseChatModel) -> ReflectionResult:
    grounded = deterministic_checks(goal, draft)
    grounded_report = "\n".join(f"- {issue}" for issue in grounded) or "- Deterministic checks passed."
    # This can be done better, how should it be done?
    critique_response = llm.invoke([
        ("system", "You are a separate critic. Judge against the rubric; do not rewrite the draft."),
        ("human", f"""Goal: {goal}
Rubric: correctness, completeness, internal consistency, and instruction adherence.
External deterministic checks:
{grounded_report}

Draft:
{draft}

List concrete issues. If there are none, respond exactly PASS."""),
    ], temperature=0.2)
    critique = critique_response.content
    if not isinstance(critique, str) or not critique.strip():
        raise RuntimeError("The chat model returned an empty or unsupported response")
    critique = critique.strip()
    if critique.strip().upper() == "PASS" and not grounded:
        revised = draft
    else:
        response = llm.invoke([
            ("system", "Revise a deliverable using both external checks and an independent critique."),
            ("human", f"Goal: {goal}\n\nDraft:\n{draft}\n\nGrounded checks:\n{grounded_report}\n\nCritique:\n{critique}\n\nReturn only the improved deliverable."),
        ], temperature=0.2)
        revised = response.content
        if not isinstance(revised, str) or not revised.strip():
            raise RuntimeError("The chat model returned an empty or unsupported response")
        revised = revised.strip()
    return ReflectionResult(draft, critique, revised, grounded)
