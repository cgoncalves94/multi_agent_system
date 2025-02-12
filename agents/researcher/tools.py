"""Researcher agent tools."""

from langchain_community.tools import TavilySearchResults
from langchain_community.document_loaders import WikipediaLoader
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import List, Dict, Any

# Initialize tools with better parameters
tavily_search = TavilySearchResults(
    max_results=5,  # number of results to return
    search_depth="advanced",  # depth of search
    include_raw_content=True,  # Get full content when available
    include_answer=True,  # Get a summarized answer
)


# Define input schemas
class WikipediaSearchInput(BaseModel):
    query: str = Field(
        description="The search query to look up on Wikipedia. Should be specific enough to find relevant articles."
    )
    max_docs: int = Field(
        default=2,
        description="Maximum number of Wikipedia documents to retrieve",
        ge=1,
        le=5,
    )


@tool("wikipedia_search", args_schema=WikipediaSearchInput)
async def wikipedia_search(query: str, max_docs: int = 2) -> List[Dict[str, Any]]:
    """Search Wikipedia for information about a topic.
    Use this for general knowledge, historical facts, and background information.
    Returns list of results in standard format with content, source, and metadata.
    """
    # Search Wikipedia (run sync operation in async context)
    try:
        import asyncio

        search_docs = await asyncio.get_event_loop().run_in_executor(
            None, lambda: WikipediaLoader(query=query, load_max_docs=max_docs).load()
        )

        # Format results to match Tavily structure
        formatted_results = []
        for doc in search_docs:
            formatted_results.append(
                {
                    "content": doc.page_content,
                    "url": doc.metadata.get("source", "wikipedia.org"),
                    "title": doc.metadata.get("title", "Wikipedia Article"),
                    "score": 1.0,  # Wikipedia results are considered highly reliable
                    "metadata": doc.metadata,
                }
            )

        return formatted_results
    except Exception as e:
        print(f"Wikipedia search error: {e}")
        return []  # Return empty list on error to allow web results to continue
