"""React Diagram Agent schemas."""

from pydantic import BaseModel, Field


class DiagramAnalysisResponse(BaseModel):
    """Response schema for diagram analysis."""

    diagram: str = Field(description="Generated Mermaid.js diagram")
    filename: str = Field(description="Name of the saved diagram file")
