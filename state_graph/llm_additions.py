# state_graph/llm_additions.py
"""
LLM call additions for state graphs.
Uses implementations from planning_lab/:
- decomposition.py → Task Decomposition
- tree_of_thoughts.py → Tree of Thoughts
- lats.py → LATS (Language Agent Tree Search)
- self_refine.py → Constrained ReAct (Self-Refine pattern)
- RAG/ → RAG retrieval
"""

import json
import asyncio
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# IMPORT IMPLEMENTATIONS FROM planning_lab/
# ============================================================

# 1. Decomposition
from planning_lab.algorithms.decomposition import decompose_goal, execute_plan, GeneratedPlan
from planning_lab.models import Plan

# 2. Tree of Thoughts
from planning_lab.algorithms.tree_of_thoughts import tree_of_thoughts, ThoughtCandidates, ThoughtEvaluation

# 3. LATS
from planning_lab.algorithms.lats import lats, LATSResult, LATSNode
from planning_lab.algorithms.environment import Environment

# 4. Self-Refine (for Constrained ReAct)
from planning_lab.algorithms.self_refine import reflect_and_refine, ReflectionResult

# 5. RAG
from RAG import get_retriever
from RAG.config import DEFAULT_RETRIEVER, DEFAULT_TOP_K

# ============================================================
# LLM INITIALIZATION
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing in .env")

# ============================================================
# LANGCHAIN COMPATIBILITY WRAPPER FOR GROQ
# ============================================================

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, HumanMessage
from langchain_core.outputs import ChatResult, ChatGeneration


class GroqChatModel(BaseChatModel):
    """
    Wrapper to make Groq compatible with LangChain's BaseChatModel.
    This allows us to use decompose_goal(), tree_of_thoughts(), lats(), etc.
    """
    
    def __init__(self, api_key: str = GROQ_API_KEY, model: str = GROQ_MODEL):
        super().__init__()
        self.api_key = api_key
        self.model = model
        self.client = Groq(api_key=api_key)
        self._temperature = 0.1
    
    def _generate(self, messages: List[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        """Generate a response from Groq."""
        formatted = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                formatted.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                formatted.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted.append({"role": "assistant", "content": msg.content})
            else:
                formatted.append({"role": "user", "content": str(msg.content)})
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=formatted,
            temperature=kwargs.get("temperature", self._temperature),
            stop=stop,
            **{k: v for k, v in kwargs.items() if k not in ['temperature', 'stop']}
        )
        
        message = AIMessage(content=response.choices[0].message.content or "")
        return ChatResult(generations=[ChatGeneration(message=message)])
    
    @property
    def _llm_type(self) -> str:
        return "groq"


# ============================================================
# 1. TASK DECOMPOSITION - Using decompose_goal()
# ============================================================

async def decompose_task(goal: str, max_tasks: int = 6) -> Dict[str, Any]:
    """
    Decompose a complex task into subtasks.
    
    This USES decompose_goal() from planning_lab/algorithms/decomposition.py
    It returns a Plan object with tasks and dependencies.
    
    The Plan object has:
    - goal: str
    - tasks: List[Task] with id, instruction, depends_on
    - execution_batches(): returns batches of parallel tasks
    - terminal_tasks(): returns tasks with no dependents
    """
    try:
        # Create Groq-compatible LangChain model
        groq_model = GroqChatModel()
        groq_model._temperature = 0.1
        
        # Call decompose_goal from planning_lab
        plan = decompose_goal(goal, groq_model)
        
        # Plan is a Plan object from planning_lab/models.py
        # Convert to dict for JSON response
        return {
            "status": "success",
            "goal": plan.goal,
            "tasks": [
                {
                    "id": task.id,
                    "instruction": task.instruction,
                    "depends_on": task.depends_on
                }
                for task in plan.tasks
            ],
            "task_count": len(plan.tasks),
            "execution_batches": [
                batch for batch in plan.execution_batches()
            ],
            "plan": plan.model_dump() if hasattr(plan, "model_dump") else str(plan)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "goal": goal,
            "tasks": [],
            "task_count": 0
        }


# ============================================================
# 2. TREE OF THOUGHTS - Using tree_of_thoughts()
# ============================================================

async def tree_of_thoughts_search(
    problem: str, 
    depth: int = 3, 
    beam_width: int = 3
) -> Dict[str, Any]:
    """
    Tree of Thoughts search.
    
    This USES tree_of_thoughts() from planning_lab/algorithms/tree_of_thoughts.py
    It returns a list of Thought objects.
    
    Each Thought has:
    - state: str (the thought/solution)
    - score: float (0-1)
    - rationale: str (why this score)
    """
    try:
        # Create Groq-compatible LangChain model
        groq_model = GroqChatModel()
        groq_model._temperature = 0.5
        
        # Call tree_of_thoughts from planning_lab
        thoughts = tree_of_thoughts(problem, groq_model, depth=depth, beam_width=beam_width)
        
        # thoughts is a list of Thought objects from planning_lab/models.py
        return {
            "status": "success",
            "thoughts": [
                {
                    "state": t.state,
                    "score": t.score,
                    "rationale": t.rationale
                }
                for t in thoughts
            ],
            "best": thoughts[0].state if thoughts else None,
            "best_score": thoughts[0].score if thoughts else 0.0,
            "thought_count": len(thoughts)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "thoughts": [],
            "best": None,
            "best_score": 0.0,
            "thought_count": 0
        }


# ============================================================
# 3. LATS - Using lats()
# ============================================================

class EnvironmentAdapter(Environment):
    """
    Adapter to connect LATS to our MCP tools and evaluators.
    """
    
    def __init__(self, evaluator_func: Optional[Callable] = None):
        self.evaluator_func = evaluator_func
    
    async def evaluate(self, state: str):
        """Evaluate a state and return feedback."""
        from planning_lab.models import EnvironmentFeedback
        
        if self.evaluator_func:
            # If it's an async function, await it
            if asyncio.iscoroutinefunction(self.evaluator_func):
                result = await self.evaluator_func(state)
            else:
                result = self.evaluator_func(state)
            
            if isinstance(result, dict):
                return EnvironmentFeedback(
                    success=result.get("success", False),
                    score=result.get("score", 0.0),
                    details=result.get("details", "")
                )
            # If result is a boolean
            return EnvironmentFeedback(
                success=bool(result),
                score=0.5 if result else 0.0,
                details=str(result)
            )
        
        # Default evaluation
        return EnvironmentFeedback(
            success=True,
            score=0.5,
            details="No evaluator provided."
        )


async def lats_search(
    task: str,
    evaluator_func: Optional[Callable] = None,
    iterations: int = 3,
    n_actions: int = 3
) -> Dict[str, Any]:
    """
    LATS: Language Agent Tree Search.
    
    This USES lats() from planning_lab/algorithms/lats.py
    It returns a LATSResult object.
    
    LATSResult has:
    - success: bool
    - output: str (the best solution)
    - best_score: float
    - iterations: int
    - root: LATSNode (the search tree)
    """
    try:
        # Create Groq-compatible LangChain model
        groq_model = GroqChatModel()
        groq_model._temperature = 0.5
        
        # Create environment with evaluator
        env = EnvironmentAdapter(evaluator_func)
        
        # Call lats from planning_lab
        result = await lats(
            task=task,
            llm=groq_model,
            environment=env,
            iterations=iterations,
            n_actions=n_actions
        )
        
        # result is a LATSResult from planning_lab/algorithms/lats.py
        return {
            "status": "success",
            "success": result.success,
            "output": result.output,
            "best_score": result.best_score,
            "iterations": result.iterations,
            "has_tree": result.root is not None
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "success": False,
            "output": None,
            "best_score": 0.0,
            "iterations": 0
        }


# ============================================================
# 4. CONSTRAINED REACT - Using reflect_and_refine()
# ============================================================

async def constrained_react_step(
    goal: str,
    draft: str,
    constraints: List[str] = None
) -> Dict[str, Any]:
    """
    Constrained ReAct using Self-Refine pattern.
    
    This USES reflect_and_refine() from planning_lab/algorithms/self_refine.py
    It implements:
    1. Deterministic checks (length, key terms, structure)
    2. LLM critique
    3. Revision based on critique
    
    The deterministic_checks in self_refine.py check:
    - Minimum word count (80 words)
    - Contains goal terms
    - Has structure (headings or list items)
    """
    try:
        # Add constraints to the goal
        full_goal = goal
        if constraints:
            full_goal = f"{goal}\n\nCONSTRAINTS:\n" + "\n".join(f"- {c}" for c in constraints)
        
        # Create Groq-compatible LangChain model
        groq_model = GroqChatModel()
        groq_model._temperature = 0.2
        
        # Call the REAL reflect_and_refine from planning_lab
        result = reflect_and_refine(full_goal, draft, groq_model)
        
        # result is a ReflectionResult from planning_lab/algorithms/self_refine.py
        return {
            "status": "success",
            "original_draft": result.draft,
            "critique": result.critique,
            "revised": result.revised,
            "grounded_issues": result.grounded_issues,
            "improved": result.revised != result.draft,
            "has_issues": len(result.grounded_issues) > 0 or result.critique != "PASS"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "original_draft": draft,
            "revised": draft,
            "improved": False
        }


# ============================================================
# 5. RAG RETRIEVAL - Using RAG
# ============================================================

def rag_retrieve(query: str, top_k: int = DEFAULT_TOP_K) -> Dict[str, Any]:
    """
    RAG retrieval using the RAG system.
    
    This uses:
    - RAG/retriever.py → get_retriever()
    - RAG/config.py → DEFAULT_RETRIEVER, DEFAULT_TOP_K
    
    The retriever.answer() method:
    1. Retrieves relevant chunks from ChromaDB
    2. Uses the retriever's specific strategy (naive, hybrid, agentic)
    3. Generates an answer using Groq
    4. Returns answer + sources
    """
    try:
        # Get the retriever from RAG/
        retriever = get_retriever(DEFAULT_RETRIEVER)
        
        # Call the answer() method
        result = retriever.answer(query)
        
        return {
            "status": "success",
            "answer": result.get("answer"),
            "sources": result.get("sources", []),
            "source_count": len(result.get("sources", []))
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "answer": None,
            "sources": [],
            "source_count": 0
        }


def rag_retrieve_sources(query: str, top_k: int = DEFAULT_TOP_K) -> List[Dict]:
    """Get only the source documents from RAG."""
    result = rag_retrieve(query, top_k)
    return result.get("sources", [])


# ============================================================
# 6. PLAN EXECUTION - Using execute_plan()
# ============================================================

async def execute_decomposed_plan(plan_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Execute a decomposed plan using execute_plan().
    
    This takes a plan (from decompose_task) and executes all tasks
    in the correct order, respecting dependencies.
    
    NOTE: The current execute_plan() in planning_lab only builds prompts
    and returns an empty dict. This is a known limitation of the original
    implementation. For full execution, you would need to implement
    the actual task execution logic.
    """
    try:
        # Reconstruct Plan object from dict
        plan = Plan(
            goal=plan_data.get("goal", ""),
            tasks=plan_data.get("tasks", [])
        )
        
        # Create Groq-compatible LangChain model
        groq_model = GroqChatModel()
        groq_model._temperature = 0.1
        
        # Call execute_plan from planning_lab
        outputs = await asyncio.to_thread(
            execute_plan,
            plan=plan,
            llm=groq_model,
            max_workers=4
        )
        
        return {
            "status": "success",
            "outputs": outputs,
            "task_count": len(outputs)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "outputs": {}
        }