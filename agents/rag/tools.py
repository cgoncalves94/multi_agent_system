"""RAG agent tools."""
from typing import Dict, List, Optional
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
import os
from langchain_core.documents import Document
from agents.config import get_embeddings, env

# Initialize components
embeddings = get_embeddings()

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)

# Use path from environment config
CHROMA_PATH = env.chroma_path

# Ensure directory exists with proper permissions
os.makedirs(CHROMA_PATH, exist_ok=True)

# Initialize vector store - Chroma handles database creation and management
vectorstore = Chroma(
    collection_name="rag_documents",
    embedding_function=embeddings,
    persist_directory=CHROMA_PATH
)

# Define input schemas
class DocumentInput(BaseModel):
    content: str = Field(description="The document content to ingest into the vector store")
    metadata: Optional[Dict] = Field(default=None, description="Optional metadata for the document")

class QueryInput(BaseModel):
    query: str = Field(description="The query to search for in the knowledge base")
    k: int = Field(
        default=4,
        description="Number of documents to retrieve",
        ge=1,
        le=10
    )

@tool("ingest_document", args_schema=DocumentInput)
async def ingest_document(content: str, metadata: Optional[Dict] = None) -> Dict:
    """Ingest and index a document into the vector store for later retrieval."""
    
    # Split document into chunks
    chunks = text_splitter.split_text(content)
    
    # Create Document objects
    documents = [
        Document(
            page_content=chunk,
            metadata=metadata or {}
        ) for chunk in chunks
    ]
    
    # Add documents to vector store
    try:
        # Generate unique IDs based on source and chunk number
        source = metadata.get('source', 'unknown') if metadata else 'unknown'
        source_base = os.path.splitext(source)[0]  # Remove extension
        ids = [f"{source_base}_chunk_{i}" for i in range(len(documents))]
        
        # Use proper document objects
        await vectorstore.aadd_documents(
            documents=documents,
            ids=ids
        )
        
        # Return success status
        return {
            "status": "success",
            "num_chunks": len(chunks),
            "metadata": metadata
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

@tool("retrieve_context", args_schema=QueryInput)
async def retrieve_context(query: str, k: int = 4) -> List[Dict]:
    """Retrieve relevant context from the vector store based on the query."""
    try:
        # Debug: Check if collection exists and has documents
        collection = vectorstore._collection
        count = collection.count()
        
        # Adjust k to not exceed document count
        k = min(k, count) if count > 0 else 1
        
        # Search for relevant documents
        results = await vectorstore.asimilarity_search_with_relevance_scores(
            query,
            k=k
        )

        # Format results and normalize scores to 0-1 range
        formatted_results = []
        for doc, score in results:
            # Convert cosine similarity (-1 to 1) to 0-1 range
            normalized_score = (score + 1) / 2
            formatted_results.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": normalized_score,
                "source": "knowledge_base"
            })
        
        # Sort by score descending
        formatted_results.sort(key=lambda x: x["score"], reverse=True)
        
        return formatted_results
        
    except Exception as e:
        return [{
            "error": str(e),
            "source": "knowledge_base"
        }]



