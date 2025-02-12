"""Main graph builder that compiles all sub-graphs."""

from typing import Any
import aiosqlite
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END

from agents.schemas import (
    AgentState,
    RouterReturn,
    SynthesisReturn,
    SummaryReturn,
    AnswerReturn,
)
from agents.researcher.graph import create_research_graph
from agents.rag.graph import create_rag_graph
from agents.prompts import ROUTER_SYSTEM_PROMPT, ANSWER_PROMPT
from agents.config import get_model, env

# Initialize model for routing and summarization using shared configuration
model = get_model()

# Conditionally import SQLite components
try:
    from langgraph.checkpoint.sqlite import AsyncSqliteSaver

    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False

# Node functions


async def summarize_conversation(state: AgentState) -> SummaryReturn:
    """Summarize older messages while keeping recent context."""
    messages = state["messages"]
    summary = state.get("summary", "")

    # Create summarization prompt
    if summary:
        summary_prompt = (
            f"This is summary of the conversation to date: {summary}\n\n"
            "Extend the summary by taking into account the new messages above:"
        )
    else:
        summary_prompt = "Create a summary of the conversation above:"

    # Add prompt to history
    messages_for_summary = messages + [HumanMessage(content=summary_prompt)]
    response = await model.ainvoke(messages_for_summary)

    # Keep the last 2 messages (usually the latest human-AI exchange)
    kept_messages = messages[-2:] if len(messages) >= 2 else messages

    # Add summary as system message before the kept messages
    summary_msg = SystemMessage(
        content=f"Previous conversation summary: {response.content}"
    )

    return {
        "summary": response.content,
        "messages": [summary_msg] + kept_messages,
        "next": "route",
    }


async def synthesize_node(state: AgentState) -> SynthesisReturn:
    """Node to synthesize final response."""
    # Get the routing decision to know which response to use
    route = (
        state.get("routing_decision", "")
        .split("[Selected Route]")[1]
        .split("\n")[1]
        .strip()
        .upper()
    )

    # Case 1: Coming from RAG graph
    if route == "RAG" and (rag_response := state.get("rag_response")):
        source = rag_response.get("source")

        if source == "process_document" and (
            document_status := rag_response.get("document_status")
        ):
            return {
                "messages": [
                    AIMessage(
                        content=f"""Successfully processed document: {document_status['metadata'].get('source', 'document')}
- Number of chunks: {document_status['num_chunks']}
- Document type: {document_status['metadata'].get('type', 'unknown')}

You can now ask questions about this document!"""
                    )
                ]
            }

        if source == "answer_query" and (
            rag_analysis := rag_response.get("rag_analysis")
        ):
            # If response has [Answer], it means we found information
            has_answer = "[Answer]" in rag_analysis

            if has_answer:
                # Clean up the markers and add the "found" prefix
                content = f"""Here's what I found in the document:

{rag_analysis.replace("[Answer]", "").replace("[Sources]", "\nBased on:").strip()}"""
            else:
                # No information found, use response as-is
                content = rag_analysis

            return {"messages": [AIMessage(content=content)]}

    # Case 2: Coming from Research graph
    if route == "RESEARCH" and (research_response := state.get("research_response")):
        if research_response.get("source") == "researcher":
            return {
                "messages": [
                    AIMessage(
                        content=f"""Here are the findings from my research:

{research_response["research_findings"]}"""
                    )
                ]
            }

    # Fallback for unexpected state
    return {
        "messages": [
            AIMessage(
                content="I encountered an unexpected state and cannot provide a proper response."
            )
        ]
    }


async def route_message(state: AgentState) -> RouterReturn:
    """Router that decides if we need to delegate to specialized agents."""
    messages = state["messages"]
    if not messages:
        return {"next": "research"}  # Default to research if no messages

    # Get recent context
    recent_messages = messages[-3:] if len(messages) > 3 else messages
    recent_content = "\n".join(
        [f"{msg.__class__.__name__}: {msg.content}" for msg in recent_messages]
    )

    # Get routing decision
    response = await model.ainvoke(
        [
            SystemMessage(content=ROUTER_SYSTEM_PROMPT.format(context=recent_content)),
            HumanMessage(
                content=messages[-1].content
            ),  # Route based on last message with context
        ]
    )

    # Get the route from the response
    next_step = (
        response.content.split("[Selected Route]")[1].split("\n")[1].strip().upper()
    )

    # Map to valid next steps, defaulting to research
    route_mapping = {"ANSWER": "answer", "RESEARCH": "research", "RAG": "rag"}

    return {
        "routing_decision": response.content,  # Store full routing decision separately
        "next": route_mapping.get(
            next_step, "research"
        ),  # Default to research if unknown route
    }


# Edge conditions


def should_summarize(state: AgentState) -> bool:
    """Check if we should summarize the conversation."""
    messages = state["messages"]

    # First check message count - summarize if more than threshold
    if len(messages) > 6:  # Number of messages to summarize
        # Only summarize after an AI response (complete exchange)
        last_message = messages[-1]

        # Don't summarize if we're in the middle of a tool sequence
        if isinstance(last_message, SystemMessage):
            return False

        # Summarize after complete exchanges (Human -> AI)
        return isinstance(last_message, AIMessage)

    return False  # Don't summarize if under threshold


def route_condition(state: AgentState) -> str:
    """Determine the next node from router based on state."""
    routing_decision = state.get("routing_decision", "")
    if not routing_decision:
        return "research"

    try:
        route = (
            routing_decision.split("[Selected Route]")[1].split("\n")[1].strip().upper()
        )
        route_mapping = {"ANSWER": "answer", "RESEARCH": "research", "RAG": "rag"}
        return route_mapping.get(route, "research")
    except (IndexError, AttributeError):  # Specific exceptions instead of bare except
        return "research"


async def answer(state: AgentState) -> AnswerReturn:
    """Node for providing direct answers to simple questions."""
    messages = state["messages"]
    if not messages:
        return {"messages": []}

    # Get recent context
    recent_messages = messages[-3:] if len(messages) > 3 else messages
    recent_content = "\n".join(
        [f"{msg.__class__.__name__}: {msg.content}" for msg in recent_messages]
    )

    # Process with LLM using strict answer prompt with context
    response = await model.ainvoke(
        [
            SystemMessage(content=ANSWER_PROMPT.format(context=recent_content)),
            *messages,  # Include full message history for complete context
        ]
    )

    return {
        "messages": [response]  # Direct answers don't need synthesis
    }


# Create the main graph


def create_graph() -> Any:
    """Create and compile the complete agent graph with all components."""
    # Initialize SQLite persistence if available
    memory = None
    if SQLITE_AVAILABLE:
        try:
            conn = aiosqlite.connect(env.state_db_path)
            memory = AsyncSqliteSaver(conn)
        except Exception as e:
            print(f"Warning: Could not initialize SQLite persistence: {e}")

    # Create the main workflow graph
    workflow = StateGraph(AgentState)

    # Create and compile sub-graphs
    research_graph = create_research_graph().compile()
    rag_graph = create_rag_graph().compile()

    # Add all nodes
    workflow.add_node("router", route_message)
    workflow.add_node("answer", answer)
    workflow.add_node("research", research_graph)
    workflow.add_node("rag", rag_graph)
    workflow.add_node("summarize", summarize_conversation)
    workflow.add_node("synthesize", synthesize_node)

    # Start directly with router (no summarize check at start)
    workflow.add_edge(START, "router")

    # Normal routing paths
    workflow.add_conditional_edges(
        "router",
        route_condition,
        {"answer": "answer", "research": "research", "rag": "rag"},
    )

    # Research and RAG synthesis
    workflow.add_edge("research", "synthesize")
    workflow.add_edge("rag", "synthesize")

    # Check for summarization only after responses
    workflow.add_conditional_edges(
        "synthesize", should_summarize, {True: "summarize", False: END}
    )
    workflow.add_conditional_edges(
        "answer", should_summarize, {True: "summarize", False: END}
    )

    # After summarization, end turn
    workflow.add_edge("summarize", END)

    return workflow.compile(checkpointer=memory)
