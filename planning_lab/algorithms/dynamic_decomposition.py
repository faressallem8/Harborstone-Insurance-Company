# planning_lab/algorithms/dynamic_decomposition.py

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict


class DynamicDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    done: bool
    next_task: str


def dynamic_decomposition(
    goal: str,
    llm: BaseChatModel,
    max_steps: int = 4,
) -> list[tuple[str, str, dict]]:
    """
    Dynamic decomposition: interleaved planning and execution.
    Returns history of (task, result, metadata).
    """
    history: list[tuple[str, str, dict]] = []
    for step in range(max_steps):
        observation = "\n".join(
            f"{task}: {result}" for task, result, _ in history
        ) or "None"

        decision = llm.with_structured_output(
            DynamicDecision,
            method="json_mode",
        ).invoke([
            ("system", "You are an adaptive planner. Use prior observations before deciding what comes next. Return your response as a valid JSON object."),
            ("human", f"""Goal: {goal}
Completed work and observations:
{observation}

Decide the single best next task. Set done to true only when the goal is met.
When done is true, use an empty string for next_task.
Return JSON."""),
        ], temperature=0.1)

        if decision.done:
            break

        task = decision.next_task.strip()
        if not task:
            raise ValueError(f"Dynamic planner omitted next_task at step {step + 1}")

        # Execute the task (LLM reasoning)
        response = llm.invoke([
            ("system", "Execute the next adaptive sub-task using the observations provided."),
            ("human", f"Goal: {goal}\nNext task: {task}\nPrior observations:\n{observation}"),
        ], temperature=0.2)

        result = response.content
        if not isinstance(result, str) or not result.strip():
            raise RuntimeError("The chat model returned an empty or unsupported response")
        result = result.strip()

        # Store with metadata
        metadata = {
            "step": step + 1,
            "success": True,
            "type": "llm",
        }
        history.append((task, result, metadata))

    return history


def has_divergence(history: list[tuple[str, str, dict]]) -> bool:
    """Check if divergence occurred during dynamic decomposition."""
    return any(meta.get("diverged", False) for _, _, meta in history)


def get_failed_tasks(history: list[tuple[str, str, dict]]) -> list[dict]:
    """Get all failed tasks from history."""
    return [
        {"task": task, "result": result, "metadata": meta}
        for task, result, meta in history
        if meta.get("success") is False
    ]