"""File utility functions for the multi-agent system."""

import os
from typing import Dict, Any, List
import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Initialize tokenizer once
_tokenizer = tiktoken.get_encoding("cl100k_base")


async def count_tokens(text: str) -> int:
    """Count the number of tokens in a text using cl100k_base encoding.

    Args:
        text: The text to count tokens for

    Returns:
        Number of tokens in the text
    """
    return len(_tokenizer.encode(text))


async def create_chunks(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """Split text into chunks using RecursiveCharacterTextSplitter with token counting.

    This function uses a hybrid approach that:
    - Uses exact token counting for size control
    - Respects sentence and paragraph boundaries
    - Maintains semantic coherence
    - Handles markdown and code blocks appropriately

    Args:
        text: Text to split into chunks
        chunk_size: Target size for each chunk in tokens
        chunk_overlap: Number of tokens to overlap between chunks

    Returns:
        List of text chunks
    """
    # Initialize the recursive splitter with token counting
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=lambda x: len(_tokenizer.encode(x)),
        separators=["\n\n", "\n", ".", "!", "?", " ", ""],  # Ordered by priority
        keep_separator=True,  # Keep the separator with the chunk
        is_separator_regex=False,  # Treat separators as literal strings
    )

    # Split the text
    chunks = text_splitter.split_text(text)

    return chunks


async def read_file(file_path: str) -> Dict[str, Any]:
    """Read file content and return with metadata.

    Args:
        file_path: Path to the file relative to test_docs directory

    Returns:
        Dict containing:
        - content: The file content as string
        - metadata: File metadata (source, type, extension)
        - error: Error message if any
    """
    try:
        # Ensure path is within test_docs directory for safety
        base_dir = "data/test_docs"
        full_path = os.path.join(base_dir, os.path.basename(file_path))

        if not os.path.exists(full_path):
            return {
                "error": f"File not found: {file_path}",
                "content": "",
                "metadata": {},
            }

        with open(full_path, "r") as f:
            content = f.read()

        return {
            "content": content,
            "metadata": {
                "source": os.path.basename(file_path),
                "type": "documentation",
                "extension": os.path.splitext(file_path)[1],
            },
        }

    except Exception as e:
        return {"error": f"Error reading file: {str(e)}", "content": "", "metadata": {}}
