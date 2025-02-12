"""Researcher agent graph definition."""

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from src.agents.researcher.prompts import QUERY_EXTRACTION_PROMPT, SYNTHESIS_PROMPT
from src.agents.researcher.tools import tavily_search, wikipedia_search
from src.agents.researcher.schemas import (
    ResearchOutputState,
    ResearchState,
    SearchQueries,
    ResearchResponse,
)
from src.config import get_model
from src.utils import format_conversation_history, get_recent_messages

# Initialize model using shared configuration
model = get_model()


# Nodes
async def extract_query(state: ResearchState) -> ResearchState:
    """Extract optimized search queries for different sources."""
    messages = state.get("messages", [])
    if not messages:
        return {"web_query": "", "wiki_query": ""}

    # Get recent context, excluding the current message
    context = format_conversation_history(
        get_recent_messages(messages, exclude_last=True)
    )

    # Use structured output for query extraction
    response = await model.with_structured_output(SearchQueries).ainvoke(
        [
            SystemMessage(content=QUERY_EXTRACTION_PROMPT.format(context=context)),
            HumanMessage(content=messages[-1].content),
        ]
    )

    return {"web_query": response.web_query, "wiki_query": response.wiki_query}


async def web_search_node(state: ResearchState) -> ResearchState:
    """Node for web search that directly uses tavily."""
    query = state.get("web_query", "")
    if not query:
        return {"web_results": ""}

    raw_results = await tavily_search.ainvoke(query)

    web_results = "\n\n---\n\n".join(
        [
            f"""<Document href="{result.get("url", "Unknown")}">
            {result["content"]}
            </Document>"""
            for result in raw_results
        ]
    )

    return {
        "web_results": web_results  # Only return what we need
    }


async def wiki_search_node(state: ResearchState) -> ResearchState:
    """Node for wiki search that directly uses wikipedia."""
    query = state.get("wiki_query", "")
    if not query:
        return {"wiki_results": ""}

    raw_results = await wikipedia_search.ainvoke({"query": query, "max_docs": 2})

    wiki_results = "\n\n---\n\n".join(
        [
            f'<Document source="Wikipedia" title="{result.get("title", "Wikipedia Article")}">\n{result["content"]}\n</Document>'
            for result in raw_results
        ]
    )

    return {
        "wiki_results": wiki_results  # Only return what we need
    }


async def combine_results(state: ResearchState) -> ResearchOutputState:
    """Node to combine and synthesize search results."""
    # Get results from both search states
    web_results = state.get("web_results", "")
    wiki_results = state.get("wiki_results", "")

    # Combine the pre-formatted results
    synthesis_text = "Web Search Results:\n" + web_results
    synthesis_text += "\n\nWikipedia Results:\n" + wiki_results

    # Synthesize findings
    response = await model.ainvoke(
        [
            SystemMessage(content=SYNTHESIS_PROMPT),
            HumanMessage(
                content=f"Please synthesize these search results:\n\n{synthesis_text}"
            ),
        ]
    )

    # Return research response with source
    return ResearchOutputState(
        research_response=ResearchResponse(
            research_findings=response.content, source="researcher"
        )
    )


# Graph
def create_research_graph() -> StateGraph:
    """Create the research sub-graph without compiling."""
    # Create graph with proper state typing
    workflow = StateGraph(ResearchState, output=ResearchOutputState)

    # Add nodes
    workflow.add_node("extract_query", extract_query)
    workflow.add_node("web_search", web_search_node)
    workflow.add_node("wiki_search", wiki_search_node)
    workflow.add_node("combine", combine_results)

    # Flow:
    # 1. First extract the query
    workflow.add_edge(START, "extract_query")

    # 2. Then do parallel searches with extracted query
    workflow.add_edge("extract_query", "web_search")
    workflow.add_edge("extract_query", "wiki_search")

    # 3. Both searches feed into combine
    workflow.add_edge("web_search", "combine")
    workflow.add_edge("wiki_search", "combine")

    # 4. Final step
    workflow.add_edge("combine", END)

    return workflow
