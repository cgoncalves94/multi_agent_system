"""Core schemas for agent system."""
from typing import List, Dict, Optional, Any, TypedDict
from langgraph.graph import MessagesState
from langchain_core.messages import BaseMessage

class AgentState(MessagesState):
    """Base state for all agents."""
    summary: str = ""                                  # For conversation summarization
    research_response: Optional[Dict[str, Any]] = None # Complete research response with source
    rag_response: Optional[Dict[str, Any]] = None      # Complete RAG response with source
    routing_decision: Optional[str] = None             # Router's decision for next step

# Router Return Types
class RouterReturn(TypedDict):
    """Return type for router node."""
    routing_decision: Optional[str]
    next: str

class SynthesisReturn(TypedDict):
    """Return type for synthesis node."""
    messages: List[BaseMessage]

class SummaryReturn(TypedDict):
    """Return type for summary node."""
    summary: str
    messages: List[BaseMessage]
    next: str

class AnswerReturn(TypedDict):
    """Return type for answer node."""
    messages: List[BaseMessage]

