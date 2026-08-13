import asyncio
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field

# Import allowed tools from models.py for consistency
from planning_lab.models import ALLOWED_TOOLS


# ============================================================
# REAL HARBORSTONE MCP TOOLS
# ============================================================
AVAILABLE_TOOLS_STR = ", ".join(ALLOWED_TOOLS)
# ============================================================


class DynamicDecision(BaseModel):
    """Structured output for dynamic planning."""
    model_config = ConfigDict(extra="forbid")

    done: bool
    next_task: str
    tool: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


async def dynamic_decomposition(
    goal: str,
    llm: BaseChatModel,
    mcp_session,
    max_steps: int = 5,
) -> list[tuple[str, str, dict]]:
    """
    Dynamic decomposition: interleaved planning and execution with MCP.
    Returns history of (task, result, metadata).
    """
    history: list[tuple[str, str, dict]] = []
    alternative_suggestion = None  # Carry alternative to next step

    for step in range(max_steps):
        observation = "\n".join(
            f"{task}: {result}" for task, result, _ in history
        ) or "None"

        # 1. LLM decides next task
        # If there's an alternative suggestion, inject it
        if alternative_suggestion:
            decision = DynamicDecision(
                done=False,
                next_task=alternative_suggestion["task"],
                tool=alternative_suggestion.get("tool"),
                params=alternative_suggestion.get("params", {})
            )
            alternative_suggestion = None  # Clear it
        else:
            decision = llm.with_structured_output(
                DynamicDecision,
                method="json_schema",
            ).invoke([
                ("system", f"""You are an adaptive planner. Use prior observations before deciding what comes next.
Available tools: {AVAILABLE_TOOLS_STR}
If a tool call fails, suggest an alternative approach.
If the last task failed, suggest a different approach.
For MCP tasks, specify the tool and params.""",),
                ("human", f"""Goal: {goal}
Completed work and observations:
{observation}

Decide the single best next task. Set done to true only when the goal is met.
When done is true, use an empty string for next_task."""),
            ], temperature=0.1)

        if decision.done:
            break

        task = decision.next_task.strip()
        if not task:
            raise ValueError(f"Dynamic planner omitted next_task at step {step + 1}")

        # 2. Execute the task with tool validation
        if decision.tool:
            # Validate tool - consistent with decomposition-first
            if decision.tool not in ALLOWED_TOOLS:
                raise ValueError(f"Task '{task}' uses unknown tool: {decision.tool}")

            # MCP Execution
            try:
                result = await mcp_session.call_tool(decision.tool, decision.params)
                metadata = {
                    "step": step + 1,
                    "tool": decision.tool,
                    "params": decision.params,
                    "success": True,
                    "type": "mcp"
                }
                history.append((task, str(result), metadata))

            except Exception as e:
                error_msg = str(e)
                metadata = {
                    "step": step + 1,
                    "tool": decision.tool,
                    "params": decision.params,
                    "success": False,
                    "error": error_msg,
                    "diverged": True,
                    "type": "mcp_failure"
                }
                history.append((task, f"ERROR: {error_msg}", metadata))

                # LLM suggests alternative for NEXT iteration
                alt_decision = llm.with_structured_output(
                    DynamicDecision,
                    method="json_schema",
                ).invoke([
                    ("system", f"The previous task failed. Suggest an alternative approach. Tools: {AVAILABLE_TOOLS_STR}"),
                    ("human", f"""Goal: {goal}
Failed task: {task}
Error: {error_msg}
Suggest an alternative next task that can continue the investigation.
Set done=True only if the goal cannot be completed.""")
                ], temperature=0.2)

                if not alt_decision.done and alt_decision.next_task:
                    alternative_suggestion = {
                        "task": alt_decision.next_task,
                        "tool": alt_decision.tool,
                        "params": alt_decision.params
                    }
                    # This will be executed in the NEXT iteration

        else:
            # LLM Execution (reasoning/analysis)
            response = llm.invoke([
                ("system", "Execute the next adaptive sub-task using the observations provided."),
                ("human", f"Goal: {goal}\nNext task: {task}\nPrior observations:\n{observation}"),
            ], temperature=0.2)

            result = response.content
            if not isinstance(result, str) or not result.strip():
                raise RuntimeError("The chat model returned an empty or unsupported response")

            metadata = {
                "step": step + 1,
                "tool": "reasoning",
                "success": True,
                "type": "llm"
            }
            history.append((task, result.strip(), metadata))

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