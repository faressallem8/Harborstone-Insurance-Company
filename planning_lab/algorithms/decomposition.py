from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field

from ..models import Plan, ALLOWED_TOOLS


# ============================================================
# REAL HARBORSTONE MCP TOOLS
# ============================================================
HARBORSTONE_TOOLS = f"""
Available MCP Tools:
- check_claim_status(claim_id) → returns claim status and details [Anyone]
- get_customer_info(customer_id) → returns customer information [Anyone]
- get_policy_details(policy_id) → returns policy information [Anyone]
- file_claim(policy_id, amount, description) → files a new claim [Anyone]
- assess_risk(policy_id) → returns risk assessment [Anyone]
- approve_claim(claim_id, decision, notes) → approves/denies claim [Requires: Underwriter, Risk Analyst, or Admin]

Note: approve_claim requires elevated privileges and may fail for non-privileged users.
"""

PLANNER_SYSTEM = f"""You are a careful task-decomposition planner.
Produce a small executable DAG, not a prose checklist. Every task must make a concrete
contribution to the goal. Independent research or analysis tasks should be parallel.
The plan must end with exactly one synthesis task depending on every necessary branch.

{HARBORSTONE_TOOLS}

Every task that can be fulfilled by an MCP tool should specify:
- tool: the exact tool name from the list above
- params: the parameters required by that tool

If a task cannot be fulfilled by a single MCP tool, describe what analysis or reasoning is needed in the instruction.
"""
# ============================================================


class PlannedTask(BaseModel):
    """Wire schema for LLM-generated tasks."""
    model_config = ConfigDict(extra="forbid")

    id: str
    instruction: str
    depends_on: list[str]
    tool: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class GeneratedPlan(BaseModel):
    """Schema for LLM-generated plan."""
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=5)
    tasks: list[PlannedTask] = Field(min_length=3, max_length=6)


def decompose_goal(goal: str, llm: BaseChatModel) -> Plan:
    """Generate a complete DAG plan upfront."""
    generated = llm.with_structured_output(
        GeneratedPlan,
        method="json_schema",
    ).invoke([
        ("system", PLANNER_SYSTEM),
        ("human", f"""Decompose this goal into 3-6 tasks: {goal!r}
Use short task ids such as t1, t2, etc.
Dependencies may refer only to tasks in the plan.
For each task that uses an MCP tool, specify the tool name and parameters.
Preserve the supplied goal exactly in the plan's goal field."""),
    ], temperature=0.1)

    payload = generated.model_dump()
    payload["goal"] = goal

    # Plan validation will handle tool validation via model_validator
    return Plan.model_validate(payload)


async def _execute_mcp_tool_async(mcp_session, tool_name: str, params: dict, task_id: str) -> str:
    """Execute MCP tool asynchronously."""
    try:
        result = await mcp_session.call_tool(tool_name, params)
        return str(result)
    except Exception as e:
        return f"ERROR: {str(e)}"


async def _execute_llm_task_async(llm: BaseChatModel, prompt: str, task_id: str) -> str:
    """Execute LLM reasoning task asynchronously."""
    try:
        response = llm.invoke([
            ("system", "You execute one node in a validated task DAG."),
            ("human", prompt),
        ], temperature=0.2)
        content = response.content
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("The chat model returned an empty or unsupported response")
        return content.strip()
    except Exception as e:
        return f"ERROR: {str(e)}"


async def execute_plan(
    plan: Plan,
    llm: BaseChatModel,
    mcp_session,
    max_workers: int = 4,
) -> dict[str, str]:
    """Execute a decomposition plan with MCP tools with parallel limit."""
    outputs: dict[str, str] = {}
    semaphore = asyncio.Semaphore(max_workers)

    async def _execute_with_limit(coro):
        async with semaphore:
            return await coro

    for batch in plan.execution_batches():
        tasks = []
        task_ids = []

        for task_id in batch:
            task = plan.task(task_id)
            context = "\n\n".join(
                f"OUTPUT FROM {dependency}:\n{outputs[dependency]}"
                for dependency in task.depends_on
            ) or "No prerequisite outputs."

            if task.tool:
                # MCP task with semaphore
                tasks.append(
                    _execute_with_limit(
                        _execute_mcp_tool_async(
                            mcp_session,
                            task.tool,
                            task.params,
                            task_id
                        )
                    )
                )
            else:
                # LLM reasoning task
                prompt = f"""Overall goal: {plan.goal}
Current task: {task.instruction}
Prerequisite outputs:
{context}
Complete only the current task. Be concrete and concise."""
                tasks.append(
                    _execute_with_limit(
                        _execute_llm_task_async(
                            llm,
                            prompt,
                            task_id
                        )
                    )
                )
            task_ids.append(task_id)

        # Execute all tasks in parallel with limit
        results = await asyncio.gather(*tasks)

        for task_id, result in zip(task_ids, results):
            outputs[task_id] = result

    return outputs


def final_output(plan: Plan, outputs: dict[str, str]) -> str:
    """Get the final synthesis output."""
    terminals = plan.terminal_tasks()
    if len(terminals) != 1:
        raise ValueError(f"Expected exactly one terminal synthesis task, found {terminals}")
    return outputs[terminals[0]]