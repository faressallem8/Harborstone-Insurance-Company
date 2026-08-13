# planning_lab/algorithms/environment.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

# ============================================================
# EnvironmentFeedback defined here for standalone import
# ============================================================
class EnvironmentFeedback(BaseModel):
    """Feedback from environment after executing an action."""
    success: bool
    score: float = Field(ge=0.0, le=1.0)
    feedback: str = Field(default="")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)
# ============================================================


class Environment:
    """
    Abstract environment for LATS/Reflexion.
    Should be replaced with real HarborstoneEnvironment.
    """
    
    def __init__(self):
        pass
    
    async def evaluate(self, action: str, context: Dict[str, Any]) -> EnvironmentFeedback:
        """
        Evaluate an action in the environment.
        This is a placeholder - replace with real implementation.
        """
        # Placeholder implementation
        return EnvironmentFeedback(
            success=True,
            score=1.0,
            feedback="Action executed successfully (placeholder)",
            details={"action": action, "context": context}
        )