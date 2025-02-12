"""Researcher agent schemas."""

from typing import TypedDict, Optional
from pydantic import BaseModel, Field
from agents.schemas import AgentState


# Research Response Schema
class ResearchResponse(TypedDict):
    """Structure for Research responses."""

    research_findings: Optional[str] = None
    source: str = "researcher"  # Always "researcher" for this graph


# Input State
class ResearchState(AgentState):
    """State for research agent with search results."""

    web_query: str = ""
    wiki_query: str = ""
    web_results: str = ""
    wiki_results: str = ""


# Output State
class ResearchOutputState(TypedDict):
    """Final output state for research operations."""

    research_response: ResearchResponse


# Structured Outputs
class SearchQueries(BaseModel):
    """Structure for search queries"""

    web_query: str = Field(
        description="Query optimized for web search, focused on recent and broad information"
    )
    wiki_query: str = Field(
        description="Query optimized for Wikipedia, focused on historical and factual information"
    )
