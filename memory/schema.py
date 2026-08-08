from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field
from memory.types import Metadata, MessageContent

class RoleEnum(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class MessageType(str, Enum):
    CHAT = "chat"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    SUMMARY = "summary"
    SYSTEM = "system"

class StructuredSummaryData(BaseModel):
    summary: str
    facts: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    timeline: List[str] = Field(default_factory=list)
    decisions: List[str] = Field(default_factory=list)

class Message(BaseModel):
    conversation_id: str
    message_id: str
    sequence: int
    insert_after_sequence: Optional[int] = None
    display_order: Optional[int] = None
    role: RoleEnum
    msg_type: MessageType = MessageType.CHAT
    content: MessageContent
    structured_summary: Optional[StructuredSummaryData] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    token_count: int = 0
    metadata: Metadata = Field(default_factory=dict)
    tool_calls: Optional[List[Metadata]] = None
    tool_call_id: Optional[str] = None
    is_masked: bool = False
    
    parent_summary_id: Optional[str] = None
    children_summary_ids: List[str] = Field(default_factory=list)
    summary_level: int = 0

    version: str = "1.0"
    checksum: Optional[str] = None
    compression_method: Optional[str] = None
    embedding_version: Optional[str] = None
    retrieval_score: Optional[float] = None
    expires_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    embedding_id: Optional[str] = None
    document_id: Optional[str] = None
    source: Optional[str] = None

class ShortTermMemorySnapshot(BaseModel):
    sequence_counter: int
    current_token_usage: int
    scratchpad_state: Metadata
    messages_references: List[Message]


class Scratchpad(BaseModel):
    goal: Optional[str] = None
    plan: List[str] = Field(default_factory=list)
    current_subgoal: Optional[str] = None
    completed_steps: List[str] = Field(default_factory=list)
    working_state: Metadata = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ShortTermMemoryState(BaseModel):
    messages: List[Message] = Field(default_factory=list)
    scratchpad: Scratchpad = Field(default_factory=Scratchpad)
    current_token_usage: int = 0
    max_token_limit: int = 4000    