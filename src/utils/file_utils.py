"""File utility functions for the multi-agent system."""

import os
from typing import Dict, Any, List
import tiktoken

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
    """Split text into chunks based on token count.

    Args:
        text: Text to split into chunks
        chunk_size: Target size for each chunk in tokens
        chunk_overlap: Number of tokens to overlap between chunks

    Returns:
        List of text chunks
    """
    chunks = []
    current_chunk = []
    current_length = 0

    # Split into sentences (simple approach)
    sentences = text.split(". ")

    for sentence in sentences:
        sentence = sentence.strip() + "."
        sentence_length = len(_tokenizer.encode(sentence))

        if current_length + sentence_length > chunk_size:
            # Save current chunk
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            # Start new chunk with overlap
            if chunks:
                # Get last few sentences from previous chunk
                overlap_sentences = current_chunk[-2:]  # Adjust based on overlap needs
                current_chunk = overlap_sentences + [sentence]
                current_length = sum(len(_tokenizer.encode(s)) for s in current_chunk)
            else:
                current_chunk = [sentence]
                current_length = sentence_length
        else:
            current_chunk.append(sentence)
            current_length += sentence_length

    # Add the last chunk if it exists
    if current_chunk:
        chunks.append(" ".join(current_chunk))

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
