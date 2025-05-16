"""RAG tools for knowledge agent."""

from typing import Dict, List, Optional

from langchain_chroma import Chroma
from langchain_core.tools import tool
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.tools import TavilySearchResults
from pydantic import BaseModel, Field

from backend.config import settings

# Initialize components
embeddings = settings.get_embeddings()
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)


# Define a relevance score normalization function
def normalize_score(score: float) -> float:
    """Normalize the relevance score to be between 0 and 1."""
    # Convert from [-1, 1] range to [0, 1] range
    return max(0.0, min(1.0, (score + 1) / 2))


# Initialize vector store with the normalization function
vectorstore = Chroma(
    collection_name="rag_documents",
    embedding_function=embeddings,
    persist_directory=str(settings.chroma_path),
    relevance_score_fn=normalize_score,
)


# Input schemas
class DocumentInput(BaseModel):
    content: str = Field(
        description="The document content to ingest into the vector store"
    )
    metadata: Optional[Dict] = Field(
        default=None, description="Optional metadata for the document"
    )


class QueryInput(BaseModel):
    query: str = Field(description="The query to search for in the knowledge base")
    k: int = Field(
        default=5, description="Number of documents to retrieve", ge=1, le=10
    )


@tool("retrieve_context", args_schema=QueryInput)
async def retrieve_context(query: str, k: int = 5) -> List[Dict]:
    """Retrieve relevant documents from the knowledge base based on the query."""
    try:
        # Search for relevant documents
        results = await vectorstore.asimilarity_search_with_relevance_scores(query, k=k)

        # Format results
        formatted_results = []
        for doc, score in results:
            # Extract safe metadata
            metadata = {}
            if doc.metadata:
                for key in ["source", "path", "type", "extension"]:
                    if key in doc.metadata:
                        metadata[key] = str(doc.metadata[key])

            # Add formatted result
            formatted_results.append(
                {
                    "content": doc.page_content,
                    "metadata": metadata,
                    "score": score,  # Score should already be normalized by Chroma
                    "source": "internal",
                }
            )

        # Sort by score (highest first)
        formatted_results.sort(key=lambda x: x["score"], reverse=True)
        return formatted_results

    except Exception as e:
        return [{"error": str(e), "source": "internal"}]


# Web search tool
tavily_search = TavilySearchResults(
    max_results=5,
    search_depth="advanced",
    include_raw_content=True,
    include_answer=True,
)
