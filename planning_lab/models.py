from __future__ import annotations

from typing import Any, Iterator, Optional, Dict
from pydantic import BaseModel, ConfigDict, Field, model_validator
import networkx as nx


# ============================================================
# ALLOWED TOOLS - Defined here for validation in Plan
# ============================================================
ALLOWED_TOOLS = {
    "check_claim_status",
    "get_customer_info",
    "get_policy_details",
    "file_claim",
    "assess_risk",
    "approve_claim"
}
# ============================================================


# ============================================================
# EnvironmentFeedback for LATS/Reflexion
# ============================================================
class EnvironmentFeedback(BaseModel):
    """Feedback from environment after executing an action."""
    success: bool
    score: float = Field(ge=0.0, le=1.0)
    feedback: str = Field(default="")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)
# ============================================================


# ============================================================
# Thought for Tree of Thoughts
# ============================================================
class Thought(BaseModel):
    """A thought node in Tree of Thoughts search."""
    state: str
    score: float = Field(default=0.0)
    rationale: str = Field(default="")
    parent: Optional[str] = None
    depth: int = Field(default=0)
# ============================================================


class Task(BaseModel):
    """A single node in a decomposed plan."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$")
    instruction: str = Field(min_length=5)
    depends_on: list[str] = Field(default_factory=list)

    # MCP tool information
    tool: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    """Complete decomposition DAG with validation."""

    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=5)
    tasks: list[Task] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dag(self) -> "Plan":
        """Validate DAG structure: no duplicates, no missing deps, no cycles, exactly one synthesis."""
        task_ids = {task.id for task in self.tasks}

        # 1. Check duplicate IDs
        if len(task_ids) != len(self.tasks):
            raise ValueError("Duplicate task IDs found")

        # 2. Check dependencies exist
        for task in self.tasks:
            for dep in task.depends_on:
                if dep not in task_ids:
                    raise ValueError(f"Task {task.id} depends on {dep} which does not exist")

        # 3. Check self-dependency
        for task in self.tasks:
            if task.id in task.depends_on:
                raise ValueError(f"Task {task.id} depends on itself")

        # 4. Build graph and check cycles
        g = nx.DiGraph()
        for task in self.tasks:
            g.add_node(task.id)
            for dep in task.depends_on:
                g.add_edge(dep, task.id)

        if not nx.is_directed_acyclic_graph(g):
            raise ValueError("Cycle detected in task graph")

        # 5. Exactly one terminal task (synthesis)
        terminals = [n for n in g.nodes if g.out_degree(n) == 0]
        if len(terminals) != 1:
            raise ValueError(
                f"Expected exactly one terminal (synthesis) task, found {len(terminals)}: {terminals}"
            )

        # 6. Validate tools
        for task in self.tasks:
            if task.tool and task.tool not in ALLOWED_TOOLS:
                raise ValueError(
                    f"Task {task.id} uses unknown tool: {task.tool}. "
                    f"Allowed tools: {', '.join(ALLOWED_TOOLS)}"
                )

        return self

    def task(self, task_id: str) -> Task:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(f"Task {task_id} not found")

    def execution_batches(self) -> Iterator[list[str]]:
        """Yield batches of tasks that can run in parallel."""
        g = nx.DiGraph()
        for task in self.tasks:
            g.add_node(task.id)
            for dep in task.depends_on:
                g.add_edge(dep, task.id)

        remaining = set(task.id for task in self.tasks)
        while remaining:
            batch = [
                node for node in remaining
                if all(dep not in remaining for dep in g.predecessors(node))
            ]
            if not batch:
                raise ValueError("Deadlock detected in task graph")
            yield batch
            remaining -= set(batch)

    def terminal_tasks(self) -> list[str]:
        """Return tasks with no outgoing dependencies (synthesis tasks)."""
        g = nx.DiGraph()
        for task in self.tasks:
            g.add_node(task.id)
            for dep in task.depends_on:
                g.add_edge(dep, task.id)
        return [n for n in g.nodes if g.out_degree(n) == 0]

    def is_acyclic(self) -> bool:
        """Check if the task graph is acyclic."""
        g = nx.DiGraph()
        for task in self.tasks:
            g.add_node(task.id)
            for dep in task.depends_on:
                g.add_edge(dep, task.id)
        return nx.is_directed_acyclic_graph(g)