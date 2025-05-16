"""Summarizer agent graph definition."""

from typing import Any, Dict, List, Optional

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from backend.agents.summarizer.schemas import (
    ChunkSizeRecommendation,
    ChunkState,
    ProcessDocumentNodeOutput,
    SummarizerOutput,
    SummarizerState,
)
from backend.agents.summarizer.prompts import (
    CHUNK_SIZE_PROMPT,
    CHUNK_SUMMARY_PROMPT,
)
from backend.agents.summarizer.tools import chunk_document
from backend.config import settings
from backend.utils.file_utils import count_tokens

# Initialize model using shared configuration
model = settings.get_model()


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


async def process_document_node(state: SummarizerState) -> Dict[str, Any]:
    """
    Node to process and chunk an input document.
    It expects the document text to be already populated in the state.
    """
    doc_content_from_orchestrator = getattr(state, "document_content", None)
    doc_content_from_input = getattr(state, "input_document_content", None)

    document_to_process: Optional[str] = None
    error_source_field = ""

    if doc_content_from_orchestrator and doc_content_from_orchestrator.strip():
        document_to_process = doc_content_from_orchestrator
        error_source_field = "document_content (from orchestrator)"
    elif doc_content_from_input and doc_content_from_input.strip():
        document_to_process = doc_content_from_input
        error_source_field = "input_document_content (direct input)"

    if not document_to_process:
        final_summary_update = (
            "Error: No document content found. Checked state fields "
            "'document_content' and 'input_document_content'. "
            "Content must be provided in one of these fields."
        )
        return ProcessDocumentNodeOutput(
            document="",
            chunks=[],
            summaries=[],
            final_summary=final_summary_update,
        ).model_dump(exclude_none=True)

    try:
        chunk_settings = await analyze_document_structure(document_to_process)
        chunk_result = await chunk_document.ainvoke(
            {
                "text": document_to_process,
                "chunk_size": chunk_settings["chunk_size"],
                "chunk_overlap": chunk_settings["chunk_overlap"],
            }
        )
    except Exception as e:
        return ProcessDocumentNodeOutput(
            document=document_to_process,
            chunks=[],
            summaries=[],
            final_summary=f"Error during document analysis or chunking: {str(e)}",
        ).model_dump(exclude_none=True)

    if "error" in chunk_result or not chunk_result.get("chunks"):
        error_message = chunk_result.get(
            "error", "No chunks produced or an unspecified error occurred."
        )
        return ProcessDocumentNodeOutput(
            document=document_to_process,
            chunks=[],
            summaries=[],
            final_summary=f"Error chunking document (source: {error_source_field}): {error_message}",
        ).model_dump(exclude_none=True)

    return ProcessDocumentNodeOutput(
        document=document_to_process,
        chunks=chunk_result["chunks"],
        summaries=[],
        final_summary=None,
    ).model_dump(exclude_none=True)


async def summarize_chunk(state: ChunkState) -> Dict[str, List[str]]:
    """Node to summarize an individual chunk."""
    chunk = state.chunk
    chunk_id = state.chunk_id

    response = await model.ainvoke(
        [SystemMessage(content=CHUNK_SUMMARY_PROMPT.format(chunk=chunk))]
    )
    return {"summaries": [f"[Chunk {chunk_id}] {response.content}"]}


async def combine_summaries(state: SummarizerState) -> SummarizerOutput:
    """Node to combine all chunk summaries into a single formatted string."""
    summaries = state.summaries if hasattr(state, "summaries") else []

    # Format the individual chunk summaries into a single string
    formatted_summaries_string = (
        "\n\n".join(summaries) if summaries else "No summaries generated."
    )

    # Prepare the output dictionary matching the updated SummarizerResponse schema
    result_data = {
        "chunk_summaries": summaries,
        "formatted_chunk_summaries": formatted_summaries_string,
        "num_chunks": len(summaries),
        "metadata": {
            "num_chunks": len(summaries),
            "avg_chunk_length": sum(len(s) for s in summaries) / len(summaries)
            if summaries
            else 0,
        },
    }

    # Return the dictionary. LangGraph will use this to update state.summarizer_response
    return SummarizerOutput(summarizer_response=result_data)


# Edge functions
def distribute_chunks(state: SummarizerState) -> List[Send]:
    """Creates Send objects for each chunk to be processed in parallel."""
    chunks = state.chunks if hasattr(state, "chunks") else []
    if not chunks:
        return []

    return [
        Send("summarize_chunk", ChunkState(chunk=chunk, chunk_id=i))
        for i, chunk in enumerate(chunks)
    ]


# Create the graph
def create_summarizer_graph() -> StateGraph:
    """Create the summarizer workflow graph."""
    # Initialize the graph with our state type. Output is implicitly the state update.
    workflow = StateGraph(
        SummarizerState, output=SummarizerOutput
    )  # Removed output=SummarizerOutput

    # Add nodes
    workflow.add_node("process_document", process_document_node)
    workflow.add_node("summarize_chunk", summarize_chunk)
    workflow.add_node(
        "combine_summaries", combine_summaries
    )  # This node now formats the output

    # Add edges
    workflow.add_edge(START, "process_document")

    # Add conditional edges for parallel processing
    workflow.add_conditional_edges(
        "process_document", distribute_chunks, ["summarize_chunk"]
    )

    # Connect summarize_chunk to combine_summaries
    # All parallel summarize_chunk nodes will feed into combine_summaries
    workflow.add_edge("summarize_chunk", "combine_summaries")

    # After combining summaries, the subgraph finishes
    workflow.add_edge("combine_summaries", END)

    return workflow
