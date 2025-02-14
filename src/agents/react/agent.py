"""React Diagram Agent setup using create_react_agent."""

from langgraph.prebuilt import create_react_agent
from src.config import get_model
from .schemas import DiagramAnalysisResponse
from .prompts import DIAGRAM_ANALYZER_PROMPT, STRUCTURED_OUTPUT_PROMPT
from .tools import create_mermaid_diagram, save_diagram

# List of tools available to the agent
tools = [create_mermaid_diagram, save_diagram]


def create_diagram_analyzer():
    """Create and configure the diagram analyzer react agent."""

    # Initialize the agent with our custom configuration
    react_agent = create_react_agent(
        model=get_model(),
        tools=tools,
        prompt=DIAGRAM_ANALYZER_PROMPT,  # Main agent prompt
        response_format=(
            STRUCTURED_OUTPUT_PROMPT,
            DiagramAnalysisResponse,
        ),  # Structured output prompt and schema
    )

    return react_agent
