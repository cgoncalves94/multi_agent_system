"""Schemas for the summarizer agent."""

from typing import TypedDict, Annotated, Optional
import operator
from pydantic import BaseModel, Field
from src.agents.orchestrator.schemas import AgentState


class ChunkSizeRecommendation(BaseModel):
    """Structured output for chunk size recommendation."""

    chunk_size: int = Field(
        description="Recommended chunk size in tokens", gt=99, lt=4001
    )
    chunk_overlap: int = Field(
        description="Recommended overlap size in tokens", gt=19, lt=501
    )
    reasoning: str = Field(description="Brief explanation for the recommendation")


class ChunkState(TypedDict):
    """State for processing individual document chunks."""

    chunk: str
    chunk_id: int


class SummarizerState(AgentState):
    """Main state for the summarizer agent."""

    document: str = ""  # Original document
    chunks: list[str] = []  # Document split into chunks
    summaries: Annotated[
        list[str], operator.add
    ] = []  # Individual chunk summaries (uses add reducer)
    final_summary: Optional[str] = None  # Final combined summary


class SummarizerResponse(BaseModel):
    """Response from the summarizer agent."""

    chunk_summaries: list[str]
    final_summary: str
    num_chunks: int
    metadata: dict  # Additional info like processing time, chunk sizes, etc.


class SummarizerOutput(TypedDict):
    """Output state for the summarizer agent."""

    summarizer_response: SummarizerResponse
