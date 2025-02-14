"""Main graph builder that compiles all sub-graphs."""

from typing import Any
import aiosqlite
from langchain_core.messages import (
    SystemMessage,
    AIMessage,
    HumanMessage,
    RemoveMessage,
)
from langgraph.graph import StateGraph, START, END

from src.agents.orchestrator.schemas import (
    AgentState,
    RouterReturn,
    SynthesisReturn,
    SummaryReturn,
    AnswerReturn,
)
from src.agents.researcher.graph import create_research_graph
from src.agents.rag.graph import create_rag_graph
from src.agents.summarizer.graph import create_summarizer_graph
from src.agents.react.agent import create_diagram_analyzer
from src.agents.orchestrator.prompts import ROUTER_SYSTEM_PROMPT, ANSWER_PROMPT
from src.config import get_model, env

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

    # Keep only the last exchange (2 messages) and add summary
    messages_to_delete = messages[:-2] if len(messages) > 2 else []
    delete_messages = [RemoveMessage(id=m.id) for m in messages_to_delete]

    # Add summary as system message before the kept messages
    summary_msg = SystemMessage(
        content=f"Previous conversation summary: {response.content}"
    )

    return {
        "summary": response.content,
        "messages": delete_messages + [summary_msg],
        "next": "route",
    }


async def synthesize_node(state: AgentState) -> SynthesisReturn:
    """Node to synthesize final response."""
    # Get the routing decision to know which response to use
    routing_decision = state.get("routing_decision", "")

    try:
        route = (
            routing_decision.split("[Selected Route]")[1].split("\n")[1].strip().upper()
        )
    except Exception:
        route = ""

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

    # Case 3: Coming from Diagram Generator
    if route == "DIAGRAM":
        # Get structured output
        structured_output = state.get("structured_response")
        messages = state["messages"]
        current_human_idx = None

        # Find the current human message
        for idx in range(len(messages) - 1, -1, -1):
            if isinstance(messages[idx], HumanMessage):
                current_human_idx = idx
                break

        if current_human_idx is None:
            return {"messages": [AIMessage(content="No query found to process.")]}

        # Get messages after the human query
        subsequent_messages = messages[current_human_idx + 1 :]
        messages_to_delete = [RemoveMessage(id=m.id) for m in subsequent_messages]

        # Check if we have a valid diagram
        if structured_output and hasattr(structured_output, "diagram"):
            # Clean up the diagram (remove mermaid wrapper if present)
            diagram = structured_output.diagram
            if "```mermaid" in diagram:
                diagram = diagram.split("```mermaid\n")[1].split("```")[0]

            final_message = AIMessage(
                content=f"""I've created a visual representation of the components and their relationships.

The Mermaid.js diagram has been generated and saved to: {structured_output.filename}

Here's the diagram content:

{diagram}

You can now ask questions about the diagram!"""
            )
            return {"messages": messages_to_delete + [final_message]}
        else:
            # No diagram was generated, return a message explaining this
            final_message = AIMessage(
                content="""I apologize, but I wasn't able to generate a diagram for this request.

To create a diagram, I need to:
1. Analyze the content
2. Create a Mermaid.js diagram using the create_mermaid_diagram tool
3. Save it using the save_graph tool

Please try rephrasing your request, specifying what kind of diagram you'd like (flowchart, gantt chart, etc.) and what elements should be included."""
            )
            return {"messages": messages_to_delete + [final_message]}

    # Case 4: Coming from Summarizer graph
    if route == "SUMMARIZE" and (summarizer_output := state.get("summarizer_response")):
        # Handle both dictionary and direct Pydantic model cases
        try:
            if isinstance(summarizer_output, dict):
                response = summarizer_output.get("summarizer_response")
            else:
                response = summarizer_output

            if not response:
                raise ValueError("No valid summarizer response found")

            return {
                "messages": [
                    AIMessage(
                        content=f"""Here's the summary I generated:

{response.final_summary}

Document Statistics:
- Number of chunks processed: {response.num_chunks}"""
                    )
                ]
            }
        except Exception as e:
            print(f"Error processing summarizer response: {e}")
            return {
                "messages": [
                    AIMessage(
                        content="I encountered an error while processing the summary."
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
    route_mapping = {
        "ANSWER": "answer",
        "RESEARCH": "research",
        "RAG": "rag",
        "SUMMARIZE": "doc_summarize",
        "DIAGRAM": "diagram_analyze",
    }

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
    if len(messages) > 10:  # Only summarize after 10 messages
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

        # Special handling for summarize route
        if route == "SUMMARIZE":
            # Always route to doc_summarize - it can handle both direct text and previous content
            return "doc_summarize"

        route_mapping = {
            "ANSWER": "answer",
            "RESEARCH": "research",
            "RAG": "rag",
            "SUMMARIZE": "doc_summarize",
            "DIAGRAM": "diagram_analyze",
        }
        return route_mapping.get(route, "research")
    except (IndexError, AttributeError):
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

    # Initialize the graph
    workflow = StateGraph(AgentState)

    # Create and compile sub-graphs
    research_graph = create_research_graph().compile()
    rag_graph = create_rag_graph().compile()
    summarizer_graph = create_summarizer_graph().compile()
    diagram_generator = create_diagram_analyzer()

    # Add all nodes
    workflow.add_node("router", route_message)
    workflow.add_node("answer", answer)
    workflow.add_node("research", research_graph)
    workflow.add_node("rag", rag_graph)
    workflow.add_node("summarize", summarize_conversation)  # Chat history summarizer
    workflow.add_node("doc_summarize", summarizer_graph)  # Document summarizer
    workflow.add_node("diagram_analyze", diagram_generator)  # Diagram generation
    workflow.add_node("synthesize", synthesize_node)

    # Start directly with router
    workflow.add_edge(START, "router")

    # Normal routing paths
    workflow.add_conditional_edges(
        "router",
        route_condition,
        {
            "answer": "answer",
            "research": "research",
            "rag": "rag",
            "doc_summarize": "doc_summarize",
            "diagram_analyze": "diagram_analyze",
        },
    )

    # All paths lead to synthesis
    workflow.add_edge("research", "synthesize")
    workflow.add_edge("rag", "synthesize")
    workflow.add_edge("doc_summarize", "synthesize")
    workflow.add_edge("diagram_analyze", "synthesize")

    # Check for chat history summarization after responses
    workflow.add_conditional_edges(
        "synthesize", should_summarize, {True: "summarize", False: END}
    )
    workflow.add_conditional_edges(
        "answer", should_summarize, {True: "summarize", False: END}
    )

    # After chat history summarization, end turn
    workflow.add_edge("summarize", END)

    return workflow.compile(checkpointer=memory)
