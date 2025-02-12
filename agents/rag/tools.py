"""RAG agent tools."""
from typing import Dict, List, Optional, Any
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

CHROMA_PATH = "data/chroma_db"  # Path for persistent storage
os.makedirs(CHROMA_PATH, exist_ok=True)
os.chmod(CHROMA_PATH, 0o777)  # Add write permissions to directory

# Also ensure the database file has write permissions if it exists
db_file = os.path.join(CHROMA_PATH, "chroma.sqlite3")
if os.path.exists(db_file):
    os.chmod(db_file, 0o666)  # Add write permissions to database file

# Initialize vector store
vectorstore = Chroma(
    collection_name="rag_documents",
    embedding_function=embeddings,
    persist_directory=CHROMA_PATH
)

# Define input schemas
class DocumentInput(BaseModel):
    content: str = Field(description="The document content to process and store")
    metadata: Optional[Dict] = Field(default=None, description="Optional metadata for the document")

class QueryInput(BaseModel):
    query: str = Field(description="The query to search for in the knowledge base")
    k: int = Field(
        default=4,
        description="Number of documents to retrieve",
        ge=1,
        le=10
    )

@tool("process_document", args_schema=DocumentInput)
async def process_document(content: str, metadata: Optional[Dict] = None) -> Dict:
    """Process and store a document in the vector store."""
    print(f"\n[DEBUG] Starting document processing")
    print(f"[DEBUG] Content length: {len(content)}")
    print(f"[DEBUG] Metadata: {metadata}")
    
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
        ids = [f"doc_{i}" for i in range(len(documents))]
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
        print(f"[DEBUG] Error in process_document: {str(e)}")
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
        
        # Search for relevant documents
        print(f"[DEBUG] Searching for: {query}")
        results = await vectorstore.asimilarity_search_with_relevance_scores(
            query,
            k=k
        )
        print(f"[DEBUG] Found {len(results)} results")
        
        # Format results
        formatted_results = [{
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": score,
            "source": "knowledge_base"
        } for doc, score in results]
        
        print(f"[DEBUG] Formatted results: {formatted_results}")
        return formatted_results
        
    except Exception as e:
        print(f"[DEBUG] Error in retrieve_context: {str(e)}")
        return [{
            "error": str(e),
            "source": "knowledge_base"
        }]

async def read_file(file_path: str) -> Dict[str, Any]:
    """Read file content and return with metadata."""
    try:
        # Ensure path is within test_docs directory for safety
        base_dir = "data/test_docs"
        full_path = os.path.join(base_dir, os.path.basename(file_path))
        
        if not os.path.exists(full_path):
            return {
                "error": f"File not found: {file_path}",
                "content": "",
                "metadata": {}
            }
            
        with open(full_path, 'r') as f:
            content = f.read()
            
        return {
            "content": content,
            "metadata": {
                "source": os.path.basename(file_path),
                "type": "documentation",
                "extension": os.path.splitext(file_path)[1]
            }
        }
        
    except Exception as e:
        return {
            "error": f"Error reading file: {str(e)}",
            "content": "",
            "metadata": {}
        }

