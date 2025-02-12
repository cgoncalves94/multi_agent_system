"""Utility to inspect Chroma vector store contents."""

import os
import json
import subprocess
from typing import Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


console = Console()


def format_metadata(metadata: Dict[str, Any]) -> str:
    """Format metadata for display."""
    return "\n".join(f"{k}: {v}" for k, v in metadata.items())


def display_documents(documents: Dict[str, Any]) -> None:
    """Display documents in a rich table."""
    table = Table(title="Chroma Documents")
    table.add_column("Content Preview", style="green")
    table.add_column("Metadata", style="yellow")

    # Safely get document components
    contents = documents.get("documents", [])
    metadatas = documents.get("metadatas", [])

    # Ensure we have the essential components
    if not all(isinstance(x, list) for x in [contents, metadatas]):
        console.print("[yellow]Warning: Essential document components are missing[/]")
        return

    # Create a list of tuples with content, metadata, and source for sorting
    doc_list = []
    for i in range(len(contents)):
        content = contents[i] if i < len(contents) else ""
        metadata = metadatas[i] if i < len(metadatas) else {}
        source = metadata.get("source", "") if metadata else ""
        doc_list.append((content, metadata, source))

    # Sort by source name
    doc_list.sort(key=lambda x: x[2])

    # Display sorted documents
    for content, metadata, _ in doc_list:
        content_preview = (
            content[:100] + "..." if content and len(content) > 100 else content
        )
        table.add_row(str(content_preview), format_metadata(metadata or {}))

    console.print(table)


def get_docker_container_id() -> str:
    """Get the langgraph API container ID."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=langgraph-api", "--format", "{{.ID}}"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception as e:
        console.print(f"[red]Error getting container ID:[/red] {str(e)}")
        return ""


def inspect_docker_chroma() -> None:
    """Inspect Chroma DB inside Docker container."""
    container_id = get_docker_container_id()
    if not container_id:
        console.print("[red]No running langgraph-api container found!")
        return

    try:
        # Copy the inspection script to container
        script_content = """
import os
import json
from langchain_chroma import Chroma

# Initialize Chroma with the same configuration as the main application
CHROMA_PATH = "/deps/multi_agent_system/data/chroma_db"
vectorstore = Chroma(
    collection_name="rag_documents",
    persist_directory=CHROMA_PATH
)

try:
    # Use Chroma's API to get collection info
    collection = vectorstore._collection
    count = collection.count()

    # Get all documents and their metadata
    # Note: limit=count ensures we get all documents
    documents = collection.get(
        include=['documents', 'metadatas'],
        limit=count  # Get all documents
    )

    # Add IDs which are always included
    if not documents:
        documents = {
            'documents': [],
            'metadatas': []
        }

    print(json.dumps({
        "count": count,
        "documents": documents
    }))
except Exception as e:
    print(json.dumps({
        "error": str(e),
        "count": 0,
        "documents": {
            'documents': [],
            'metadatas': []
        }
    }))
"""
        # Save temporary script
        with open("/tmp/inspect_chroma.py", "w") as f:
            f.write(script_content)

        # Copy script to container
        subprocess.run(
            ["docker", "cp", "/tmp/inspect_chroma.py", f"{container_id}:/tmp/"]
        )

        # Run script in container
        result = subprocess.run(
            ["docker", "exec", container_id, "python", "/tmp/inspect_chroma.py"],
            capture_output=True,
            text=True,
        )

        # Parse results
        data = json.loads(result.stdout)

        if "error" in data:
            console.print(f"[red]Error querying Chroma:[/red] {data['error']}")
            return

        console.print(
            Panel(
                f"[bold green]Found {data['count']} documents in Docker Chroma database[/]"
            )
        )

        if data["documents"].get("documents"):  # Check if we have any documents
            # Display statistics
            console.print("\n[bold]Collection Statistics:[/]")
            console.print(f"Total Documents: {len(data['documents']['documents'])}")

            # Get unique sources from metadata
            sources = set()
            for metadata in data["documents"]["metadatas"]:
                if metadata and "source" in metadata:
                    sources.add(metadata["source"])
            console.print(f"Unique Sources: {len(sources)}")
            if sources:
                console.print("Source files:", ", ".join(sorted(sources)))

            # Display documents
            display_documents(data["documents"])
        else:
            console.print("[yellow]No documents found in the collection.")

    except Exception as e:
        console.print(f"[red]Error inspecting Docker Chroma DB:[/red] {str(e)}")
    finally:
        # Cleanup
        if os.path.exists("/tmp/inspect_chroma.py"):
            os.remove("/tmp/inspect_chroma.py")


def main():
    """Main inspection function."""
    inspect_docker_chroma()


if __name__ == "__main__":
    main()
