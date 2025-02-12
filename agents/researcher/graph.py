"""Researcher agent graph definition."""
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from agents.researcher.prompts import QUERY_EXTRACTION_PROMPT, SYNTHESIS_PROMPT
from agents.researcher.tools import tavily_search, wikipedia_search
from agents.researcher.schemas import (
    ResearchOutputState, ResearchState, SearchQueries, ResearchResponse
)

# Initialize model
model = ChatOpenAI(
    model="gpt-4o",
    temperature=0.7,
    streaming=True
)


async def extract_query(state: ResearchState) -> ResearchState:
    """Extract optimized search queries for different sources."""
    message = state["messages"][-1].content if state.get("messages") else ""
    if not message:
        return {"web_query": "", "wiki_query": ""}
    
    # Use structured output for query extraction - using ainvoke for async
    response = await model.with_structured_output(SearchQueries).ainvoke([
        SystemMessage(content=QUERY_EXTRACTION_PROMPT),
        HumanMessage(content=message)
    ])
    
    return {
        "web_query": response.web_query,
        "wiki_query": response.wiki_query
    }

async def web_search_node(state: ResearchState) -> ResearchState:
    """Node for web search that directly uses tavily."""
    query = state.get("web_query", "")
    if not query:
        return {"web_results": ""}

    raw_results = await tavily_search.ainvoke(query)
    
    web_results = "\n\n---\n\n".join(
        [
            f'''<Document href="{result.get("url", "Unknown")}">
            {result["content"]}
            </Document>'''
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
    response = await model.ainvoke([
        SystemMessage(content=SYNTHESIS_PROMPT),
        HumanMessage(content=f"Please synthesize these search results:\n\n{synthesis_text}")
    ])
    
    # Return research response with source
    return ResearchOutputState(
        research_response=ResearchResponse(
            research_findings=response.content,
            source="researcher"
        )
    )

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