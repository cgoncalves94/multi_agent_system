"""Summarizer agent tools."""

from typing import Any, Dict

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from backend.utils.file_utils import count_tokens, create_chunks


# Define input schemas
class ChunkDocumentInput(BaseModel):
    """Input schema for document chunking."""

    text: str = Field(description="The text content to split into chunks")
    chunk_size: int = Field(
        default=500,
        description="Target size for each chunk in tokens",
        ge=100,
        le=4000,
    )
    chunk_overlap: int = Field(
        default=50,
        description="Number of tokens to overlap between chunks",
        ge=20,
        le=500,
    )


@tool("chunk_document", args_schema=ChunkDocumentInput)
async def chunk_document(
    text: str, chunk_size: int = 500, chunk_overlap: int = 50
) -> Dict[str, Any]:
    """Split a document into chunks while preserving context and sentence boundaries.

    Args:
        text: The document text to split
        chunk_size: Target size for each chunk in tokens
        chunk_overlap: Number of tokens to overlap between chunks

    Returns:
        Dictionary containing chunks and metadata about the chunking process
    """
    if not text:
        return {"chunks": [], "error": "No text provided"}

    try:
        chunks = await create_chunks(text, chunk_size, chunk_overlap)
        total_tokens = await count_tokens(text)
        chunk_tokens = [await count_tokens(c) for c in chunks]

        return {
            "chunks": chunks,
            "num_chunks": len(chunks),
            "metadata": {
                "avg_chunk_size": sum(chunk_tokens) / len(chunks),
                "num_chunks": len(chunks),
                "total_tokens": total_tokens,
            },
        }
    except Exception as e:
        return {"chunks": [], "error": f"Error chunking document: {str(e)}"}
