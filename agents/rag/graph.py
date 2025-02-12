"""RAG agent graph definition."""
from typing import Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
import re

from agents.rag.prompts import (
    QUERY_OPTIMIZATION_PROMPT,
    CONTEXT_ANALYSIS_PROMPT,
    ANSWER_GENERATION_PROMPT,
    DOCUMENT_PROCESSING_PROMPT
)
from agents.rag.tools import ingest_document, retrieve_context
from agents.rag.schemas import (
    RAGState, 
    RAGOutputState,
    OptimizedQuery,
    RAGResponse
)
from utils.file_utils import read_file


# Initialize model
model = ChatOpenAI(
    model="gpt-4o",
    temperature=0.7,
    streaming=True
)

# Utility function

def format_conversation_history(messages: List[Any]) -> str:
    """Format conversation history for context."""
    formatted_messages = []
    for msg in messages:
        prefix = 'USER' if isinstance(msg, HumanMessage) else 'ASSISTANT'
        clean_content = re.sub(r'\n+', '\n', msg.content.strip())
        formatted_messages.append(f"{prefix}: {clean_content}")
    return "\n".join(formatted_messages)

# Nodes

async def optimize_query_node(state: RAGState) -> RAGState:
    """Node to optimize query for semantic search."""
    message = state["messages"][-1].content if state.get("messages") else ""
    if not message:
        return RAGState(
            optimized_query="",
            original_query="",
            next=END
        )
    
    response = await model.with_structured_output(OptimizedQuery).ainvoke([
        SystemMessage(content=QUERY_OPTIMIZATION_PROMPT.format(
            context=format_conversation_history(state["messages"][-3:])
        )),
        HumanMessage(content=f"Optimize this query for semantic search: {message}")
    ])
    
    return RAGState(
        optimized_query=response.query,
        original_query=message,
        next="retrieve"
    )

async def analyze_context_node(state: RAGState) -> RAGState:
    """Node to analyze retrieved context."""
    optimized_query = state.get("optimized_query", "")
    context = state.get("context", [])
    
    if not optimized_query or not context:
        return RAGState(
            **state,
            analysis="No context to analyze",
            next=END
        )
    
    # Sort context by relevance score
    sorted_context = sorted(context, key=lambda x: float(x.get('score', 0)), reverse=True)
    
    # Format context with dynamic fields
    context_entries = []
    for doc in sorted_context:
        entry = ["Content:", doc.get('content', '')]
        if score := doc.get('score'):
            entry.extend(["Relevance:", f"{float(score):.3f}"])
        if source := doc.get('source'):
            entry.extend(["Source:", source])
        if metadata := doc.get('metadata'):
            entry.extend(["Additional Info:", str(metadata)])
        context_entries.append("\n".join(entry))
    
    context_text = "\n\n---\n\n".join(context_entries)
    
    response = await model.ainvoke([
        SystemMessage(content=CONTEXT_ANALYSIS_PROMPT.format(
            query=optimized_query,
            context=context_text
        ))
    ])
    
    return RAGState(
        **state,
        analysis=response.content,
        next="answer_query"
    )

async def process_document_node(state: RAGState) -> RAGOutputState:
    """Node for ingesting and indexing documents."""
    messages = state["messages"]
    if not messages:
        return RAGOutputState(
            rag_response=RAGResponse(
                document_status=None,
                rag_analysis=None,
                source="process_document"
            )
        )
    
    last_message = messages[-1].content
    
    # Extract potential file name from message
    file_pattern = r'[\w-]+\.(md|txt|py|json|yaml|yml)' 
    file_match = re.search(file_pattern, last_message)
    
    if file_match:
        # Found a file reference
        file_name = file_match.group(0)
        document = await read_file(file_name)
        
        if document.get("error"):
            return RAGOutputState(
                rag_response=RAGResponse(
                    document_status={"error": f"Could not read file {file_name}: {document['error']}"},
                    rag_analysis=None,
                    source="process_document"
                )
            )
    else:
        # Check if it's a direct content submission
        if any(marker in last_message.lower() for marker in ["here's the content", "here is the content", "process this content", "index this:"]):
            document = {
                "content": last_message,
                "metadata": {"type": "inline", "source": "chat"}
            }
        else:
            return RAGOutputState(
                rag_response=RAGResponse(
                    document_status={"error": "No valid file or content found to process"},
                    rag_analysis=None,
                    source="process_document"
                )
            )
    
    result = await ingest_document.ainvoke({
        "content": document["content"],
        "metadata": document.get("metadata")
    })
    
    return RAGOutputState(
        rag_response=RAGResponse(
            document_status=result,
            rag_analysis=None,
            source="process_document"
        )
    )

async def retrieve_node(state: RAGState) -> RAGState:
    """Node to retrieve relevant context."""
    optimized_query = state.get("optimized_query", "")
    
    context = await retrieve_context.ainvoke({
        "query": optimized_query,
        "k": 4
    })
    
    return RAGState(
        context=context,
        next="analyze_context"
    )

async def answer_query_node(state: RAGState) -> RAGOutputState:
    """Node to generate a focused answer based on context analysis."""
    optimized_query = state.get("optimized_query", "")
    analysis = state.get("analysis")
    
    if not optimized_query or not analysis:
        return RAGOutputState(
            rag_response=RAGResponse(
                document_status=None,
                rag_analysis="No analysis to generate answer from",
                source="answer_query"
            )
        )
    
    response = await model.ainvoke([
        SystemMessage(content=ANSWER_GENERATION_PROMPT.format(
            query=optimized_query,
            analysis=analysis
        ))
    ])
    
    return RAGOutputState(
        rag_response=RAGResponse(
            document_status=None,
            rag_analysis=response.content,
            source="answer_query"
        )
    )

# Conditional START edge
async def is_document_processing(state: RAGState) -> str:
    """Determine if this is a document processing request using semantic understanding."""
    messages = state["messages"]
    if not messages:
        return "retrieve_and_analyze"
        
    last_message = messages[-1].content
    
    # Use LLM to determine if this is a document processing request
    response = await model.ainvoke([
        SystemMessage(content=DOCUMENT_PROCESSING_PROMPT.format(message=last_message))
    ])
    
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
    
    # Conditional START edge - now using async function
    workflow.add_conditional_edges(
        START,
        is_document_processing,
        {
            "process_document": "process_document",
            "retrieve_and_analyze": "optimize_query"
        }
    )
    
    # Add edges
    workflow.add_edge("process_document", END)
    workflow.add_edge("optimize_query", "retrieve")
    workflow.add_edge("retrieve", "analyze_context")
    workflow.add_edge("analyze_context", "answer_query")
    workflow.add_edge("answer_query", END)
    
    return workflow 