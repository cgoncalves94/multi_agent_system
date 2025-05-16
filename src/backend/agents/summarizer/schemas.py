"""Schemas for the summarizer agent."""

from typing import Annotated, Any, Dict, List, Optional

import operator

from pydantic import BaseModel, Field

from backend.agents.orchestrator.schemas import AgentState


class ChunkSizeRecommendation(BaseModel):
    """Structured output for chunk size recommendation."""

    chunk_size: int = Field(
        description="Recommended chunk size in tokens", gt=99, lt=4001
    )
    chunk_overlap: int = Field(
        description="Recommended overlap size in tokens", gt=19, lt=501
    )
    reasoning: str = Field(description="Brief explanation for the recommendation")


# State for processing individual document chunks
class ChunkState(BaseModel):
    """State for processing individual document chunks."""

    chunk: str
    chunk_id: int


# Main state for the summarizer agent
class SummarizerState(AgentState):
    """Main state for the summarizer agent."""

    input_document_content: Optional[str] = Field(
        default=None,
        description="Pre-processed text content of the document to be summarized",
    )
    document: str = Field(
        default="",
        description="Original document processed by the node (can be same as input_document_content or derived)",
    )
    chunks: List[str] = Field(
        default_factory=list, description="Document split into chunks"
    )
    summaries: Annotated[List[str], operator.add] = Field(
        default_factory=list,
        description="Individual chunk summaries (uses add reducer)",
    )
    final_summary: Optional[str] = Field(
        default=None, description="Final combined summary"
    )


# Schema for the output of process_document_node (partial update for SummarizerState)
class ProcessDocumentNodeOutput(BaseModel):
    """Defines the structure of the dictionary returned by process_document_node."""

    document: Optional[str] = None
    chunks: Optional[List[str]] = None
    summaries: Optional[List[str]] = (
        None  # Though typically initialized empty by this node
    )
    final_summary: Optional[str] = None


# Response from the summarizer agent
class SummarizerResponse(BaseModel):
    """Response from the summarizer agent."""

    chunk_summaries: List[str] = Field(
        default_factory=list
    )  # List of individual summaries
    formatted_chunk_summaries: str = Field(
        default="",
        description="Individual chunk summaries formatted as a single string",
    )
    # final_summary is removed as it's now done by the Orchestrator's answer node
    num_chunks: int = Field(default=0)
    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )  # Additional info like processing time, chunk sizes, etc.


# Output state for the summarizer agent (Using BaseModel)
class SummarizerOutput(BaseModel):
    """Output state for the summarizer agent."""

    summarizer_response: SummarizerResponse
