"""Main graph builder that compiles all sub-graphs."""

import logging
from typing import Any, Literal

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
)
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from backend.agents.orchestrator.prompts import ANSWER_PROMPT, ROUTER_SYSTEM_PROMPT
from backend.agents.orchestrator.schemas import (
    AgentState,
    AnswerReturn,
    SummaryReturn,
)
from backend.agents.knowledge.graph import create_knowledge_graph
from backend.agents.summarizer.graph import create_summarizer_graph
from backend.config import settings

# Initialize model for routing and summarization using shared configuration
model = settings.get_model()


# Node functions


async def summarize_conversation(state: AgentState) -> SummaryReturn:
    """Summarize older messages while keeping recent context."""
    messages = state.messages
    summary = state.summary

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

    # Keep only the last exchange (2 messages) and add summary
    messages_to_delete = messages[:-2] if len(messages) > 2 else []
    delete_messages = [RemoveMessage(id=m.id) for m in messages_to_delete]

    # Add summary as system message before the kept messages
    summary_msg = SystemMessage(
        content=f"Previous conversation summary: {response.content}"
    )

    # Return SummaryReturn object
    return SummaryReturn(
        summary=response.content,
        messages=delete_messages + [summary_msg],
    )


async def route_message(
    state: AgentState,
) -> Command[Literal["answer", "knowledge", "document_summarizer"]]:
    """Router that decides if we need to delegate to specialized agents."""
    messages = state.messages
    if not messages:
        return Command(
            goto="knowledge",
            update={"routing_decision": "Default to knowledge (no messages)"},
        )

    last_message_content = messages[-1].content
    summarize_prefix = "SUMMARIZE DOCUMENT:\n\n"

    if isinstance(last_message_content, str) and last_message_content.startswith(
        summarize_prefix
    ):
        document_to_summarize = last_message_content[len(summarize_prefix) :]
        return Command(
            goto="document_summarizer",
            update={
                "document_content": document_to_summarize,
                "routing_decision": "Routing to document summarizer due to prefix.",
                "knowledge_findings": None,
                "summarizer_response": None,
            },
        )

    # Get recent context for LLM-based routing if prefix not found
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
    try:
        next_step_str = (
            response.content.split("[Selected Route]")[1].split("\n")[1].strip().upper()
        )
    except Exception:
        next_step_str = "KNOWLEDGE"  # Default to knowledge on parsing error

    # Map to valid next steps
    route_mapping = {
        "ANSWER": "answer",
        "KNOWLEDGE": "knowledge",
        "SUMMARIZE": "document_summarizer",
    }

    # Determine the actual next node name
    next_node_name = route_mapping.get(next_step_str, "knowledge")

    # Return Command to transition and update state
    return Command(goto=next_node_name, update={"routing_decision": response.content})


# Edge conditions


def should_summarize_conversation(state: AgentState) -> bool:
    """Check if we should summarize the conversation."""
    messages = state.messages

    # First check message count - summarize if more than threshold
    if len(messages) > 10:  # Only summarize after 10 messages
        # Only summarize after an AI response (complete exchange)
        last_message = messages[-1]
        return isinstance(last_message, AIMessage)
    return False


async def answer(state: AgentState) -> AnswerReturn:
    """Generate a direct answer to the user's question from conversation context."""
    messages = state.messages
    routing_decision = state.routing_decision

    try:
        # Determine which agent output we're using (if any)
        route = ""
        if routing_decision:
            try:
                route = (
                    routing_decision.split("[Selected Route]")[1]
                    .split("\n")[1]
                    .strip()
                    .upper()
                )
            except Exception:
                route = ""

        # Prepare the context for the answer based on available agent outputs
        context = ""

        # Case 1: Knowledge agent output
        if route == "KNOWLEDGE" and state.knowledge_findings:
            knowledge_data = state.knowledge_findings

            # Use the pre-formatted context if available
            if "formatted_context" in knowledge_data:
                formatted_context = knowledge_data.get("formatted_context", "")
                context = f"Context from Knowledge Agent:\n{formatted_context}\n"

        # Case 2: Summarizer agent output (from document_summarizer node)
        elif route == "SUMMARIZE" and state.summarizer_response:
            summarizer_data = state.summarizer_response
            formatted_summaries = ""
            num_chunks_processed = 0
            if isinstance(summarizer_data, dict):
                formatted_summaries = summarizer_data.get(
                    "formatted_chunk_summaries", "Summaries not available."
                )
                num_chunks_processed = summarizer_data.get("num_chunks", 0)
            elif hasattr(
                summarizer_data, "formatted_chunk_summaries"
            ):  # Check if it's an object with attributes
                formatted_summaries = getattr(
                    summarizer_data,
                    "formatted_chunk_summaries",
                    "Summaries not available.",
                )
                num_chunks_processed = getattr(summarizer_data, "num_chunks", 0)

            # Use the formatted chunk summaries as context for the answer node
            context = f"Individual Chunk Summaries:\n{formatted_summaries}\n(Processed {num_chunks_processed} chunks)\n"

        # Generate the answer
        answer_prompt_text = ANSWER_PROMPT.format(
            context=context or "No specialized context available for this query."
        )

        response = await model.ainvoke(
            messages + [SystemMessage(content=answer_prompt_text)]
        )

        return AnswerReturn(messages=[AIMessage(content=response.content)])

    except Exception as e:
        logging.error(f"Error in answer node: {e}", exc_info=True)
        return AnswerReturn(
            messages=[
                AIMessage(content="I encountered an error generating a response.")
            ]
        )


# Create the main graph


def create_graph() -> Any:
    """Create and compile the complete agent graph with all components."""

    # Initialize the graph
    workflow = StateGraph(AgentState)

    # Create and compile sub-graphs
    knowledge_graph = create_knowledge_graph().compile()
    summarizer_graph = create_summarizer_graph().compile()

    # Add all nodes
    workflow.add_node("router", route_message)
    workflow.add_node("answer", answer)
    workflow.add_node("knowledge", knowledge_graph)
    workflow.add_node("summarize_conversation", summarize_conversation)
    workflow.add_node("document_summarizer", summarizer_graph)

    # Start directly with router
    workflow.add_edge(START, "router")

    # Conditional edges from knowledge and document_summarizer nodes to chat history summarization or directly to answer
    workflow.add_conditional_edges(
        "knowledge",
        should_summarize_conversation,
        {True: "summarize_conversation", False: "answer"},
    )
    workflow.add_conditional_edges(
        "document_summarizer",
        should_summarize_conversation,
        {True: "summarize_conversation", False: "answer"},
    )

    # After chat history summarization, go to answer
    workflow.add_edge("summarize_conversation", "answer")

    # Router can also go directly to answer for simple questions not needing other agents
    # The answer node is the main one that ends the flow
    workflow.add_edge("answer", END)

    return workflow.compile()
