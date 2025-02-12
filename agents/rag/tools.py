"""RAG agent tools."""
from typing import Dict, List, Optional
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
import os
from langchain_core.documents import Document

# Initialize components
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small"  # Using text-embedding-3-small as per instructions
)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)

# Path for persistent storage in Docker container
CHROMA_PATH = "/deps/multi_agent_system/data/chroma_db"
print(f"[DEBUG] Using Chroma path: {CHROMA_PATH}")

# Ensure directory exists with proper permissions
os.makedirs(CHROMA_PATH, exist_ok=True)

# Initialize vector store - Chroma handles database creation and management
print("[DEBUG] Initializing Chroma vector store")
vectorstore = Chroma(
    collection_name="rag_documents",
    embedding_function=embeddings,
    persist_directory=CHROMA_PATH
)
print(f"[DEBUG] Initial collection count: {vectorstore._collection.count()}")

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
    print("\n[DEBUG] Starting document ingestion")
    print(f"[DEBUG] Content length: {len(content)}")
    print(f"[DEBUG] Metadata: {metadata}")
    print(f"[DEBUG] Using Chroma path: {CHROMA_PATH}")
    print(f"[DEBUG] Collection name: {vectorstore._collection.name}")
    
    # Split document into chunks
    chunks = text_splitter.split_text(content)
    print(f"[DEBUG] Created {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        print(f"[DEBUG] Chunk {i} length: {len(chunk)}")
    
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
        print(f"[DEBUG] Adding documents with IDs: {ids}")
        
        # Use proper document objects
        await vectorstore.aadd_documents(
            documents=documents,
            ids=ids
        )
        print("[DEBUG] Documents added successfully")
        
        # Verify documents were added
        count = vectorstore._collection.count()
        print(f"[DEBUG] Collection now has {count} documents")
        
        return {
            "status": "success",
            "num_chunks": len(chunks),
            "metadata": metadata
        }
    except Exception as e:
        print(f"[DEBUG] Error in ingest_document: {str(e)}")
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
        print(f"\n[DEBUG] Collection has {count} documents")
        
        # Adjust k to not exceed document count
        k = min(k, count) if count > 0 else 1
        print(f"[DEBUG] Retrieving top {k} results")
        
        # Search for relevant documents
        print(f"[DEBUG] Searching for: {query}")
        results = await vectorstore.asimilarity_search_with_relevance_scores(
            query,
            k=k
        )
        print(f"[DEBUG] Found {len(results)} results")
        
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
        
        print(f"[DEBUG] Formatted results: {formatted_results}")
        return formatted_results
        
    except Exception as e:
        print(f"[DEBUG] Error in retrieve_context: {str(e)}")
        return [{
            "error": str(e),
            "source": "knowledge_base"
        }]



