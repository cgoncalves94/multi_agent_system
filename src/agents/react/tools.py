"""React Diagram Agent tools for diagram generation and visualization."""

from typing import Dict
from langchain_core.tools import tool
from pydantic import BaseModel, Field
import os
from src.config import env


# Define input schemas
class MermaidDiagramInput(BaseModel):
    content: str = Field(
        description="""The content to visualize. Must be valid Mermaid.js syntax or will have diagram_type prepended.

Example of valid flowchart content:
    # Define main nodes first
    Main["System"]
    Auth["Authentication"]
    DB["Database"]

    # Place all relationships before subgraphs
    Main -->|"uses"| Auth
    Main -->|"connects to"| DB
    Auth -->|"stores in"| DB

    # Group related nodes in subgraphs at the end
    subgraph AuthFlow
        Login["Login"] -->|"validates"| Creds["Credentials"]
    end

    subgraph DataFlow
        Query["Query"] -->|"fetches"| Data["Data"]
    end"""
    )
    diagram_type: str = Field(
        default="graph TD",
        description="The type of Mermaid diagram (e.g., graph TD, flowchart LR, gantt, etc.).",
    )


class SaveDiagramInput(BaseModel):
    diagram: str = Field(description="The Mermaid.js diagram content to save")
    filename: str = Field(
        description="Name of the file to save the diagram to (without extension)"
    )


@tool("create_mermaid_diagram", args_schema=MermaidDiagramInput)
async def create_mermaid_diagram(content: str, diagram_type: str = "graph TD") -> Dict:
    """Create a Mermaid.js diagram from input content.

    The function will:
    1. Check if the content already starts with a valid Mermaid directive
    2. If not, prepend the specified diagram_type
    3. Return the resulting diagram

    For flowcharts/graphs:
    - Always wrap node text in double quotes: node["Node Text"]
    - Use meaningful relationship descriptions
    - Group related nodes in subgraphs when it makes sense

    For Gantt charts:
    - Include a title and dateFormat
    - Organize tasks under sections
    - Use proper date formats (YYYY-MM-DD)
    """
    known_directives = (
        "graph",
        "flowchart",
        "gantt",
        "sequenceDiagram",
        "classDiagram",
        "stateDiagram",
        "erDiagram",
    )

    # Get first non-empty line
    first_line = next(
        (line.strip() for line in content.splitlines() if line.strip()), ""
    )

    # Check if content already starts with a Mermaid directive
    if any(first_line.lower().startswith(directive) for directive in known_directives):
        diagram = content.strip()
    else:
        diagram = f"{diagram_type}\n{content.strip()}"

    return {"diagram": diagram, "type": diagram_type}


@tool("save_diagram", args_schema=SaveDiagramInput)
async def save_diagram(diagram: str, filename: str) -> Dict:
    """Save the generated Mermaid.js diagram to a file."""
    try:
        base_filename = os.path.splitext(filename)[0]
        safe_filename = "".join(c for c in base_filename if c.isalnum() or c in "._- ")
        mmd_filename = f"{safe_filename}.mmd"
        filepath = os.path.join(env.diagrams_path, mmd_filename)

        # Write raw diagram content to file
        with open(filepath, "w") as f:
            f.write(diagram)

        return {
            "filepath": filepath,
            "filename": mmd_filename,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
