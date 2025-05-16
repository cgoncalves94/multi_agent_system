"""Knowledge agent schemas for RAG system."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.agents.orchestrator.schemas import AgentState


class BinaryScore(str, Enum):
    """Binary score for relevance check."""

    YES = "yes"
    NO = "no"


class KnowledgeState(AgentState):
    """State for the knowledge agent."""

    # Query information
    query: Optional[str] = Field(default=None)
    original_query: Optional[str] = Field(default=None)

    # Document retrieval
    internal_docs: Optional[List[Dict]] = Field(default=None)
    docs_relevant: Optional[BinaryScore] = Field(default=None)
    docs_grade_explanation: Optional[str] = Field(default=None)
    docs_analysis: Optional[str] = Field(default=None)

    # External search results
    external_results: Optional[List[Dict]] = Field(default=None)

    # Processing flags
    searched_internal: bool = Field(default=False)
    searched_external: bool = Field(default=False)


class KnowledgeOutputState(BaseModel):
    """Output state containing findings to be passed to the orchestrator."""

    knowledge_findings: Dict[str, Any] = Field(
        description="Raw findings and sources for the orchestrator to synthesize"
    )
