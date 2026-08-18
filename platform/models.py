
"""Pydantic models for the platform API."""

from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class ChatRequest(BaseModel):
    agent: str
    message: str

class ChatResponse(BaseModel):
    reply: str
    agent: str

class ToolToggle(BaseModel):
    tool_name: str
    agent_name: str
    enabled: bool

class RAGDocument(BaseModel):
    name: str
    content: str
    source: Optional[str] = None
    active: bool = True