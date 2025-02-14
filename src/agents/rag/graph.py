"""RAG agent graph definition."""

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
import re
from datetime import datetime, UTC

from src.agents.rag.prompts import (
    QUERY_OPTIMIZATION_PROMPT,
    CONTEXT_ANALYSIS_PROMPT,
    ANSWER_GENERATION_PROMPT,
    DOCUMENT_PROCESSING_PROMPT,
)
from src.agents.rag.tools import ingest_document, retrieve_context
from src.agents.rag.schemas import RAGState, RAGOutputState, OptimizedQuery, RAGResponse
from src.utils.file_utils import read_file
from src.config import get_model
from src.utils import format_conversation_history, get_recent_messages

# Initialize model using shared configuration
model = get_model()


# Nodes
async def optimize_query_node(state: RAGState) -> RAGState:
    """Node to optimize query for semantic search."""
    messages = state.get("messages", [])
    if not messages:
        return RAGState(optimized_query="", original_query="", next=END)

    response = await model.with_structured_output(OptimizedQuery).ainvoke(
        [
            SystemMessage(
                content=QUERY_OPTIMIZATION_PROMPT.format(
                    context=format_conversation_history(
                        get_recent_messages(messages, exclude_last=True)
                    )
                )
            ),
            HumanMessage(
                content=f"Optimize this query for semantic search: {messages[-1].content}"
            ),
        ]
    )

    return RAGState(
        optimized_query=response.query,
        original_query=messages[-1].content,
        next="retrieve",
    )


async def analyze_context_node(state: RAGState) -> RAGState:
    """Node to analyze retrieved context."""
    optimized_query = state.get("optimized_query", "")
    context = state.get("context", [])

    if not optimized_query or not context:
        return RAGState(**state, analysis="No context to analyze", next=END)

    # Sort context by relevance score
    sorted_context = sorted(
        context, key=lambda x: float(x.get("score", 0)), reverse=True
    )

    # Format context with dynamic fields
    context_entries = []
    for doc in sorted_context:
        entry = ["Content:", doc.get("content", "")]
        if score := doc.get("score"):
            entry.extend(["Relevance:", f"{float(score):.3f}"])
        if source := doc.get("source"):
            entry.extend(["Source:", source])
        if metadata := doc.get("metadata"):
            entry.extend(["Additional Info:", str(metadata)])
        context_entries.append("\n".join(entry))

    context_text = "\n\n---\n\n".join(context_entries)

    response = await model.ainvoke(
        [
            SystemMessage(
                content=CONTEXT_ANALYSIS_PROMPT.format(
                    query=optimized_query, context=context_text
                )
            )
        ]
    )

    return RAGState(**state, analysis=response.content, next="answer_query")


async def process_document_node(state: RAGState) -> RAGOutputState:
    """Node for ingesting and indexing documents."""
    messages = state["messages"]
    if not messages:
        return RAGOutputState(
            rag_response=RAGResponse(
                document_status=None, rag_analysis=None, source="process_document"
            )
        )

    last_message = messages[-1].content

    # Get previous message if available (it might contain the actual content)
    previous_messages = state.get("messages", [])[:-1]
    previous_message = previous_messages[-1].content if previous_messages else None

    # First check for file references
    file_pattern = r"[\w-]+\.(md|txt|py|json|yaml|yml)"
    file_match = re.search(file_pattern, last_message)

    if file_match:
        # Handle file processing
        file_name = file_match.group(0)
        document = await read_file(file_name)
        if document.get("error"):
            return RAGOutputState(
                rag_response=RAGResponse(
                    document_status={
                        "error": f"Could not read file {file_name}: {document['error']}"
                    },
                    rag_analysis=None,
                    source="process_document",
                )
            )
    else:
        # Use LLM to determine if this is a request to process the previous message
        process_check = await model.ainvoke(
            [
                SystemMessage(
                    content="""Determine if this message is requesting to process or save the previous message/content into a database.
Return 'true' only if the message clearly indicates an intent to process, save, or store previous content.
Consider phrases like 'process this', 'save this', 'store this', etc.
Return 'false' otherwise."""
                ),
                HumanMessage(content=last_message),
            ]
        )

        should_process = process_check.content.strip().lower() == "true"

        if should_process and previous_message:
            # Create document from previous message with current timestamp
            current_time = datetime.now(UTC).isoformat()
            document = {
                "content": previous_message,
                "metadata": {
                    "type": "inline",
                    "source": "research_results"
                    if "research" in previous_message.lower()
                    else "chat",
                    "timestamp": current_time,
                },
            }
        else:
            return RAGOutputState(
                rag_response=RAGResponse(
                    document_status={
                        "error": "No valid file or content found to process"
                    },
                    rag_analysis=None,
                    source="process_document",
                )
            )

    result = await ingest_document.ainvoke(
        {"content": document["content"], "metadata": document.get("metadata")}
    )

    return RAGOutputState(
        rag_response=RAGResponse(
            document_status=result, rag_analysis=None, source="process_document"
        )
    )


async def retrieve_node(state: RAGState) -> RAGState:
    """Node to retrieve relevant context."""
    optimized_query = state.get("optimized_query", "")

    context = await retrieve_context.ainvoke({"query": optimized_query, "k": 4})

    return RAGState(context=context, next="analyze_context")


async def answer_query_node(state: RAGState) -> RAGOutputState:
    """Node to generate a focused answer based on context analysis."""
    optimized_query = state.get("optimized_query", "")
    original_query = state.get("original_query", "")
    analysis = state.get("analysis")

    if not optimized_query or not analysis:
        return RAGOutputState(
            rag_response=RAGResponse(
                document_status=None,
                rag_analysis="No analysis to generate answer from",
                source="answer_query",
            )
        )

    response = await model.ainvoke(
        [
            SystemMessage(
                content=ANSWER_GENERATION_PROMPT.format(
                    query=optimized_query,
                    original_query=original_query,
                    analysis=analysis,
                )
            )
        ]
    )

    return RAGOutputState(
        rag_response=RAGResponse(
            document_status=None, rag_analysis=response.content, source="answer_query"
        )
    )


# Conditional edge
async def is_document_processing(state: RAGState) -> str:
    """Determine if this is a document processing request using semantic understanding."""
    messages = state["messages"]
    if not messages:
        return "retrieve_and_analyze"

    last_message = messages[-1].content

    # Use LLM to determine if this is a document processing request
    response = await model.ainvoke(
        [SystemMessage(content=DOCUMENT_PROCESSING_PROMPT.format(message=last_message))]
    )

    # Response will be "true" or "false"
    is_processing = response.content.strip().lower() == "true"

    return "process_document" if is_processing else "retrieve_and_analyze"


# Create the RAG sub-graph
def create_rag_graph() -> StateGraph:
    """Create the RAG sub-graph without compiling."""
    workflow = StateGraph(RAGState, output=RAGOutputState)

    # Add nodes
    workflow.add_node("process_document", process_document_node)
    workflow.add_node("optimize_query", optimize_query_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("analyze_context", analyze_context_node)
    workflow.add_node("answer_query", answer_query_node)

    # Conditional START edge
    workflow.add_conditional_edges(
        START,
        is_document_processing,
        {
            "process_document": "process_document",
            "retrieve_and_analyze": "optimize_query",
        },
    )

    # Add edges
    workflow.add_edge("process_document", END)
    workflow.add_edge("optimize_query", "retrieve")
    workflow.add_edge("retrieve", "analyze_context")
    workflow.add_edge("analyze_context", "answer_query")
    workflow.add_edge("answer_query", END)

    return workflow
