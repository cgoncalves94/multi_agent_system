"""RAG agent schemas."""

from typing import List, Dict, Optional, Any
from typing_extensions import TypedDict
from pydantic import BaseModel
from src.agents.orchestrator.schemas import AgentState


# RAG Response Schema
class RAGResponse(TypedDict):
    """Structure for RAG responses."""

    document_status: Optional[Dict[str, Any]]  # From document processing
    rag_analysis: Optional[str]  # From context analysis
    source: str  # Which node generated this


# Input State
class RAGState(AgentState):
    """State for RAG agent with context management."""

    optimized_query: Optional[str] = None
    original_query: Optional[str] = None
    context: Optional[List[Dict]] = None
    analysis: Optional[str] = None


# Output State
class RAGOutputState(TypedDict):
    """Final output state for RAG operations."""

    rag_response: RAGResponse


# Structured Outputs
class OptimizedQuery(BaseModel):
    """Structured output for optimized query."""

    query: str
    reasoning: str
