"""Summarizer agent graph definition."""

from typing import List, Dict
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from src.agents.summarizer.schemas import (
    SummarizerState,
    ChunkState,
    SummarizerOutput,
    SummarizerResponse,
    ChunkSizeRecommendation,
)
from src.agents.summarizer.prompts import (
    CHUNK_SUMMARY_PROMPT,
    FINAL_SUMMARY_PROMPT,
    CHUNK_SIZE_PROMPT,
)
from src.agents.summarizer.tools import chunk_document
from src.utils import read_file
from src.utils.file_utils import count_tokens
from src.config import get_model
import re

# Initialize model using shared configuration
model = get_model()


# Node functions
async def analyze_document_structure(document: str) -> Dict[str, int]:
    """Analyze document structure and recommend chunk settings."""
    # Get document preview and stats
    preview = document[:500]
    total_tokens = await count_tokens(document)

    # Get recommendation from LLM using function calling
    recommendation = await model.with_structured_output(
        ChunkSizeRecommendation, method="function_calling"
    ).ainvoke(
        [
            SystemMessage(
                content=CHUNK_SIZE_PROMPT.format(
                    document_preview=preview,
                    metadata={
                        "total_tokens": total_tokens,
                        "total_length": len(document),
                        "has_headers": "##" in document or "#" in document,
                    },
                )
            )
        ]
    )

    return {
        "chunk_size": recommendation.chunk_size,
        "chunk_overlap": recommendation.chunk_overlap,
    }


async def process_document_node(state: SummarizerState) -> SummarizerState:
    """Node to process and chunk the input document."""
    messages = state.get("messages", [])
    if not messages:
        return SummarizerState(
            document="",
            chunks=[],
            summaries=[],
            final_summary="Error: No document provided",
        )

    # Check for previous research or RAG content to summarize
    research_response = state.get("research_response")
    rag_response = state.get("rag_response")

    # Get the content to summarize based on context
    last_message = messages[-1].content.strip()

    # First priority: Check for previous research/RAG content
    if research_response:
        document = research_response.get("research_findings", "")
    elif rag_response:
        document = rag_response.get("rag_analysis", "")
    # Second priority: Check for file references
    else:
        file_pattern = r"[\w-]+\.(md|txt|py|json|yaml|yml)"
        file_match = re.search(file_pattern, last_message)

        if file_match:
            # Found a file reference
            file_name = file_match.group(0)
            document_result = await read_file(file_name)

            if document_result.get("error"):
                return SummarizerState(
                    document="",
                    chunks=[],
                    summaries=[],
                    final_summary=f"Error reading file: {document_result['error']}",
                )

            document = document_result["content"]
        # Last priority: Use direct message content
        else:
            document = last_message

    if not document:
        return SummarizerState(
            document="",
            chunks=[],
            summaries=[],
            final_summary="Error: No content to summarize",
        )

    # Always use smart chunking for both file and direct content
    chunk_settings = await analyze_document_structure(document)

    # Process document into chunks using recommended settings
    chunk_result = await chunk_document.ainvoke(
        {
            "text": document,
            "chunk_size": chunk_settings["chunk_size"],
            "chunk_overlap": chunk_settings["chunk_overlap"],
        }
    )

    if "error" in chunk_result:
        return SummarizerState(
            document=document,
            chunks=[],
            summaries=[],
            final_summary=f"Error chunking document: {chunk_result['error']}",
        )

    return SummarizerState(
        document=document,
        chunks=chunk_result["chunks"],
        summaries=[],
        final_summary=None,
    )


async def summarize_chunk(state: ChunkState) -> SummarizerState:
    """Node to summarize an individual chunk."""
    chunk = state["chunk"]
    chunk_id = state["chunk_id"]

    # Get summary from LLM
    response = await model.ainvoke(
        [SystemMessage(content=CHUNK_SUMMARY_PROMPT.format(chunk=chunk))]
    )

    # Return the summary to be added to the summaries list
    return {"summaries": [f"[Chunk {chunk_id}] {response.content}"]}


async def combine_summaries(state: SummarizerState) -> SummarizerOutput:
    """Node to combine all chunk summaries into a final summary."""
    summaries = state.get("summaries", [])
    if not summaries:
        return SummarizerOutput(
            summarizer_response=SummarizerResponse(
                chunk_summaries=[],
                final_summary="No summaries to combine",
                num_chunks=0,
                metadata={"error": "No summaries generated"},
            )
        )

    # Format summaries for the final summarization
    formatted_summaries = "\n\n".join(summaries)

    # Get final summary from LLM
    response = await model.ainvoke(
        [
            SystemMessage(
                content=FINAL_SUMMARY_PROMPT.format(chunk_summaries=formatted_summaries)
            )
        ]
    )

    return SummarizerOutput(
        summarizer_response=SummarizerResponse(
            chunk_summaries=summaries,
            final_summary=response.content,
            num_chunks=len(summaries),
            metadata={
                "num_chunks": len(summaries),
                "avg_chunk_length": sum(len(s) for s in summaries) / len(summaries),
            },
        )
    )


# Edge functions
def distribute_chunks(state: SummarizerState) -> List[Send]:
    """Creates Send objects for each chunk to be processed in parallel."""
    chunks = state.get("chunks", [])
    if not chunks:
        return []

    # Create a Send object for each chunk
    return [
        Send("summarize_chunk", ChunkState(chunk=chunk, chunk_id=i))
        for i, chunk in enumerate(chunks)
    ]


# Create the graph
def create_summarizer_graph() -> StateGraph:
    """Create the summarizer workflow graph."""
    # Initialize the graph with our state type
    workflow = StateGraph(SummarizerState, output=SummarizerOutput)

    # Add nodes
    workflow.add_node("process_document", process_document_node)
    workflow.add_node("summarize_chunk", summarize_chunk)
    workflow.add_node("combine_summaries", combine_summaries)

    # Add edges
    workflow.add_edge(START, "process_document")

    # Add conditional edges for parallel processing
    workflow.add_conditional_edges(
        "process_document", distribute_chunks, ["summarize_chunk"]
    )

    # Connect summarize_chunk to combine_summaries
    workflow.add_edge("summarize_chunk", "combine_summaries")

    # Connect to END
    workflow.add_edge("combine_summaries", END)

    return workflow
