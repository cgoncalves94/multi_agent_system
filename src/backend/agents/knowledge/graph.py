"""Modern, agentic knowledge graph that combines internal RAG with external search."""

from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from backend.agents.knowledge.prompts import (
    QUERY_REFINEMENT_PROMPT,
    DOCUMENT_EVALUATION_PROMPT,
)
from backend.agents.knowledge.schemas import (
    BinaryScore,
    KnowledgeOutputState,
    KnowledgeState,
)
from backend.agents.knowledge.tools import retrieve_context, tavily_search
from backend.config import settings
from backend.utils import format_conversation_history, get_recent_messages

# Initialize model
model = settings.get_model()

# Define tools
tools = [retrieve_context, tavily_search]


async def refine_query(state: KnowledgeState) -> Dict[str, Any]:
    """Optimize the query for better retrieval results."""
    # Extract the query from the messages
    if not state.messages:
        return {}

    # Get the last human message as the query
    last_human_message = next(
        (
            m
            for m in reversed(state.messages)
            if hasattr(m, "type") and m.type == "human"
        ),
        None,
    )

    # Extract the raw query
    if last_human_message:
        raw_query = last_human_message.content
    # Get conversation history for context
    conversation_history = format_conversation_history(
        get_recent_messages(state.messages, exclude_last=True)
    )

    # Optimize the query using the LLM
    optimization_response = await model.ainvoke(
        [
            SystemMessage(content=QUERY_REFINEMENT_PROMPT),
            HumanMessage(
                content=f"""
            Original query: {raw_query}

            Conversation history:
            {conversation_history}

            Optimize this query for knowledge retrieval.
            """
            ),
        ]
    )

    refined_query = optimization_response.content.strip()

    return {"query": refined_query, "original_query": raw_query}


async def direct_retrieval(state: KnowledgeState) -> Dict[str, Any]:
    """Directly retrieve documents from the knowledge base using the query."""
    # Skip if no query
    if not state.query:
        return {"internal_docs": [], "searched_internal": True}

    # Call the retrieve_context tool directly
    results = await retrieve_context.ainvoke({"query": state.query, "k": 5})

    # Return the documents
    return {"internal_docs": results, "searched_internal": True}


async def check_internal_docs(state: KnowledgeState) -> Dict[str, Any]:
    """Grade document relevance and analyze content in a single step."""
    # Skip if no documents
    if not state.internal_docs:
        return {"docs_relevant": BinaryScore.NO, "searched_internal": True}

    # Get documents
    docs = state.internal_docs

    # Extract document content
    docs_text = []
    for doc in docs:
        if isinstance(doc, dict) and "content" in doc:
            docs_text.append(doc["content"])

    # If no content or query, no point evaluating
    if not docs_text or not state.query:
        return {"docs_relevant": BinaryScore.NO, "searched_internal": True}

    # Combine the documents into a single string
    context = "\n\n---\n\n".join(docs_text)

    # Make a single LLM call to evaluate and analyze the documents
    evaluation_result = await model.ainvoke(
        [
            SystemMessage(
                content=DOCUMENT_EVALUATION_PROMPT.format(
                    query=state.query, context=context
                )
            )
        ]
    )

    # Parse the structured response
    result_text = evaluation_result.content.strip()

    # Extract relevance, explanation and analysis from the structured output
    relevance = BinaryScore.NO
    explanation = "Documents do not contain relevant information."
    docs_analysis = "No relevant information found."

    for line in result_text.split("\n"):
        line = line.strip()
        if line.startswith("RELEVANT:"):
            relevance_text = line.replace("RELEVANT:", "").strip().lower()
            relevance = BinaryScore.YES if "yes" in relevance_text else BinaryScore.NO
        elif line.startswith("EXPLANATION:"):
            explanation = line.replace("EXPLANATION:", "").strip()
        elif line.startswith("ANALYSIS:"):
            docs_analysis = line.replace("ANALYSIS:", "").strip()

    # Get the rest of the analysis if it spans multiple lines
    if "ANALYSIS:" in result_text:
        analysis_parts = result_text.split("ANALYSIS:", 1)
        if len(analysis_parts) > 1:
            docs_analysis = analysis_parts[1].strip()

    return {
        "internal_docs": docs,
        "docs_relevant": relevance,
        "docs_grade_explanation": explanation,
        "docs_analysis": docs_analysis,
        "searched_internal": True,
    }


async def external_search_node(state: KnowledgeState) -> Dict[str, Any]:
    """Search external sources for information."""
    # Skip if we already have relevant internal docs
    if state.docs_relevant == BinaryScore.YES:
        return {}

    # Skip if we don't have a query
    if not state.query:
        return {"external_results": [], "searched_external": True}

    # Use the refined query for external search with proper input format
    search_results = await tavily_search.ainvoke({"query": state.query})

    # Return raw search results - prepare_output will handle formatting
    return {"external_results": search_results, "searched_external": True}


async def prepare_output(state: KnowledgeState) -> KnowledgeOutputState:
    """Formats and prepares knowledge findings from either internal documents or external search results, sorting by relevance and combining into a structured output."""

    # Initialize documents list and formatted text chunks
    documents = []
    formatted_text_chunks = []

    # Only one of these conditions will ever be true based on the graph flow
    # Process internal documents if they were relevant
    if state.docs_relevant == BinaryScore.YES and state.internal_docs:
        for i, doc in enumerate(state.internal_docs, 1):
            # Create structured document
            formatted_doc = {
                "context": doc.get("content", ""),
                "source_type": "internal",
                "source": doc.get("metadata", {}).get("source", "Unknown"),
                "score": doc.get("score", 0.0),
            }
            documents.append(formatted_doc)

            # Format as text chunk for direct LLM consumption
            source_name = doc.get("metadata", {}).get("source", "Unknown")
            text_chunk = (
                f"""Source {i} [Internal - {source_name}]: {doc.get('content', '')}"""
            )
            formatted_text_chunks.append(text_chunk)

    # Process external results if internal search failed
    elif state.external_results:
        for i, result in enumerate(state.external_results, 1):
            # Create structured document
            formatted_doc = {
                "context": result.get("content", ""),
                "source_type": "external",
                "title": result.get("title", "Unknown Title"),
                "source": result.get("url", "Unknown URL"),
                "score": result.get("score", 0.0),
            }
            documents.append(formatted_doc)

            # Format as text chunk for direct LLM consumption
            title = result.get("title", "Unknown Title")
            url = result.get("url", "Unknown URL")
            text_chunk = (
                f"""Source {i} [Web - {title} ({url})]: {result.get('content', '')}"""
            )
            formatted_text_chunks.append(text_chunk)

    # Sort documents by score (highest first)
    if documents:
        sorted_pairs = sorted(
            zip(documents, formatted_text_chunks),
            key=lambda pair: pair[0].get("score", 0),
            reverse=True,
        )
        documents, formatted_text_chunks = zip(*sorted_pairs)
        documents = list(documents)  # Convert back to list
        formatted_text_chunks = list(formatted_text_chunks)  # Convert back to list

    # Combine all text chunks into a single formatted context string
    formatted_context = "\n\n".join(formatted_text_chunks)

    # Create knowledge findings with exactly the format needed by the answer node
    knowledge_findings = {
        "documents": documents,
        "formatted_context": formatted_context,
    }

    # Return the knowledge_response with all formatted documents
    return KnowledgeOutputState(knowledge_findings=knowledge_findings)


# Create and connect the Knowledge graph
def create_knowledge_graph() -> StateGraph:
    """Create a streamlined Knowledge graph with query refinement."""
    workflow = StateGraph(KnowledgeState, output=KnowledgeOutputState)

    # Add all nodes
    workflow.add_node("refine_query", refine_query)
    workflow.add_node("retrieve", direct_retrieval)
    workflow.add_node("check_internal", check_internal_docs)
    workflow.add_node("external_search", external_search_node)
    workflow.add_node("prepare_output", prepare_output)

    # Define the streamlined flow - start with query refinement
    workflow.add_edge(START, "refine_query")
    workflow.add_edge("refine_query", "retrieve")

    # After retrieval, check if docs are relevant
    workflow.add_edge("retrieve", "check_internal")

    # Simple conditional: check where to go after internal docs check
    workflow.add_conditional_edges(
        "check_internal",
        lambda state: state.docs_relevant == BinaryScore.YES,
        {
            True: "prepare_output",  # If docs are relevant, go to output
            False: "external_search",  # If not relevant, do external search
        },
    )

    # External search goes to output preparation
    workflow.add_edge("external_search", "prepare_output")

    # Final node prepares output for orchestrator
    workflow.add_edge("prepare_output", END)

    return workflow
