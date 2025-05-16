"""Core schemas for agent system."""

from typing import Any, Dict, List, Optional, Union

from langchain_core.messages import BaseMessage
from langgraph.prebuilt.chat_agent_executor import AgentStatePydantic
from pydantic import BaseModel, Field


# Agent State
class AgentState(AgentStatePydantic):
    """Base state for all agents."""

    # Common state
    summary: Optional[str] = None
    routing_decision: Optional[str] = None

    # Agent-specific state - only one will be populated based on routing
    knowledge_findings: Optional[Dict[str, Any]] = None
    summarizer_response: Optional[Union[Dict[str, Any], Any]] = None
    document_content: Optional[str] = None


# Node Return Types


class SummaryReturn(BaseModel):
    """Return type for summary node."""

    summary: str
    messages: List[BaseMessage] = Field(default_factory=list)


class AnswerReturn(BaseModel):
    """Return type for answer node."""

    messages: List[BaseMessage] = Field(default_factory=list)
