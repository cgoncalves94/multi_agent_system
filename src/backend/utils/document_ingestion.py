"""Utility script for ingesting documents into the RAG vector store."""

import asyncio
from typing import Dict, Optional

import aiofiles
import argparse
import os
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from PyPDF2 import PdfReader

from backend.config import settings
from backend.utils.file_utils import create_chunks

from dotenv import load_dotenv

load_dotenv()

# Initialize components
embeddings = settings.get_embeddings()

# Initialize vector store - Chroma handles database creation and management
vectorstore = Chroma(
    collection_name="rag_documents",
    embedding_function=embeddings,
    persist_directory=str(settings.chroma_path),  # Ensure path is a string
)


# Define input schema for the tool
class DocumentInput(BaseModel):
    content: str = Field(
        description="The document content to ingest into the vector store"
    )
    metadata: Optional[Dict] = Field(
        default=None, description="Optional metadata for the document"
    )


@tool("ingest_document", args_schema=DocumentInput)
async def ingest_document(content: str, metadata: Optional[Dict] = None) -> Dict:
    """Ingest and index a document into the vector store for later retrieval."""
    chunk_size = 1000
    chunk_overlap = 200

    try:
        chunks = await create_chunks(content, chunk_size, chunk_overlap)
    except Exception as e:
        return {"status": "error", "error": f"Error chunking document: {str(e)}"}

    documents = [
        Document(page_content=chunk, metadata=metadata or {}) for chunk in chunks
    ]

    try:
        source = metadata.get("source", "unknown") if metadata else "unknown"
        safe_source = "".join(c for c in source if c.isalnum() or c in "._- ")
        ids = [f"{safe_source}_chunk_{i}" for i in range(len(documents))]
        await vectorstore.aadd_documents(documents=documents, ids=ids)
        return {"status": "success", "num_chunks": len(chunks), "metadata": metadata}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def ingest_file(file_path: str) -> Dict:
    """Reads a file and ingests its content into the vector store.

    Args:
        file_path: Absolute or relative path to the file

    Returns:
        Dict containing status and metadata about the ingestion
    """
    content = ""
    filename = os.path.basename(file_path)
    extension = os.path.splitext(filename)[1].lower()

    try:
        if extension == ".pdf":

            def read_pdf_content_sync(path: str) -> str:
                pdf_text = ""
                try:
                    with open(path, "rb") as f_pdf:
                        reader = PdfReader(f_pdf)
                        if reader.is_encrypted:
                            # Attempt to decrypt with an empty password, common for some PDFs
                            # More robust decryption might require user input or specific passwords
                            try:
                                reader.decrypt("")
                            except Exception:  # pylint: disable=broad-except
                                # If decryption fails, proceed but text extraction might be limited/fail
                                pass
                        for page in reader.pages:
                            page_text = page.extract_text()
                            if page_text:
                                pdf_text += page_text + "\n"
                except Exception as e_pdf:  # pylint: disable=broad-except
                    # Log or handle specific PDF reading errors if necessary
                    # For now, if PyPDF2 fails, content might remain empty or partial
                    print(f"Error reading PDF {path}: {e_pdf}")  # Basic logging
                return pdf_text.strip()

            content = await asyncio.to_thread(read_pdf_content_sync, file_path)
            if not content:  # Check if content is empty after trying to read PDF
                return {
                    "status": "error",
                    "error": f"No text content extracted from PDF: {filename}. The PDF might be image-based, encrypted, or corrupted.",
                }

        elif extension in [".txt", ".md"]:
            async with aiofiles.open(
                file_path, "r", encoding="utf-8", errors="ignore"
            ) as f:
                content = await f.read()
        else:
            return {
                "status": "error",
                "error": f"Unsupported file type: {extension}. Please upload .txt, .md, or .pdf files.",
            }

        if not content.strip():  # General check for empty content after reading
            return {
                "status": "error",
                "error": f"No text content extracted from file: {filename}",
            }

        metadata = {
            "source": filename,
            "type": "document",
            "extension": extension,
            "path": file_path,
        }

        ingestion_result = await ingest_document.ainvoke(
            {"content": content, "metadata": metadata}
        )
        return ingestion_result

    except FileNotFoundError:
        return {"status": "error", "error": f"File not found: {file_path}"}
    except Exception as e:
        return {
            "status": "error",
            "error": f"Error processing file {file_path}: {str(e)}",
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest a document into the RAG vector store."
    )
    parser.add_argument(
        "file_path", type=str, help="Path to the document file to ingest."
    )
    args = parser.parse_args()
    result = asyncio.run(ingest_file(args.file_path))

    if result.get("status") == "success":
        print(
            f"Successfully ingested document: {result.get('metadata', {}).get('source', 'Unknown')}"
        )
        print(f"Number of chunks: {result.get('num_chunks', 0)}")
    else:
        print(f"Failed to ingest document: {result.get('error', 'Unknown error')}")
