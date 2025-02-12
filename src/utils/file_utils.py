"""File utility functions for the multi-agent system."""

import os
from typing import Dict, Any


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
