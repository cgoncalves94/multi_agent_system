# Multi-Agent System

A sophisticated multi-agent system designed to answer questions by leveraging internal knowledge bases, external search, and document summarization - all orchestrated through a modern web interface.

## Overview

This system employs a suite of specialized agents orchestrated by LangGraph to handle diverse user queries. Key capabilities include:

-   🤖 **Specialized Agents**: Dedicated agents for knowledge retrieval and summarization, each optimized for their specific tasks.
-   🎯 **Intelligent Routing**: A central router analyzes incoming queries and directs them to the most suitable agent or processing path.
-   📚 **Knowledge-First Approach**: Prioritizes searching internal document base before resorting to external searches, providing properly sourced responses.
-   🔍 **External Search Integration**: Seamlessly transitions to web search when internal knowledge is insufficient, with proper citation of sources.
-   📝 **Efficient Summarization**: Processes and condenses large documents using a map-reduce approach with LLM-powered chunking.
-   🌐 **Advanced Orchestration**: Utilizes LangGraph for robust, graph-based agent coordination and conversation flow control.
-   🧠 **Contextual Conversations**: Maintains conversation history and context, with automatic summarization for longer interactions.
-   💻 **Web Interface**: Clean, responsive UI for interacting with the multi-agent system.

## System Architecture

The system's architecture revolves around a central **Router** that intelligently dispatches queries to one of several specialized processing paths:

1.  **Router**: Analyzes incoming queries to determine the optimal path:
    *   Document-based questions → **Knowledge Agent**
    *   Requests for document summarization → **Summarizer Agent**
    *   Simple, direct questions → **Quick Answer Path**

2.  **Knowledge Agent**:
    *   First searches internal vector database for relevant documents
    *   Grades retrieved documents for relevance
    *   Falls back to external search if internal documents are insufficient
    *   Formats findings with proper source attribution

3.  **Summarizer Agent**:
    *   Efficiently processes large documents using a map-reduce strategy
    *   Features smart chunking and parallel processing of summaries
    *   Produces concise summaries that maintain key information

4.  **Quick Answer Path**:
    *   Provides direct responses for straightforward queries that don't necessitate extensive processing
    *   Uses the base model's knowledge when external information isn't needed

**Intelligent Flow Control**:
All processing paths converge towards a final synthesis step to generate a unified response. The system incorporates automatic conversation summarization (after 10 messages) and adapts its end-state handling based on query complexity, conversation length, and processing needs.

## LangGraph Implementation Highlights

Our system demonstrates several key LangGraph concepts and patterns:

-   **Multi-Agent Architecture**: Implements a supervisor pattern where the orchestrator routes tasks to specialized agents and manages communication between them.

-   **Subgraphs**: Each agent is implemented as a self-contained subgraph with its own state schema and flow logic, then compiled and integrated into the main graph.

-   **Conditional Routing**: Uses LangGraph's conditional edges to implement dynamic decision-making based on document relevance, query type, and conversation state.

-   **Parallel Processing**: The summarizer agent implements map-reduce pattern for parallel document chunk processing to maximize efficiency.

-   **Streaming**: Implements token-by-token streaming to provide real-time feedback during LLM processing, with support for multiple streaming modes (values, messages, events).

-   **State Management & Persistence**: Uses structured Pydantic models for runtime state validation while leveraging LangGraph Platform's built-in persistence capabilities for maintaining conversation state across sessions without additional infrastructure.

-   **Message Memory**: Implements conversation summarization after 10 messages to maintain context while managing token limits, with semantic memory search capabilities.

-   **Tool Integration**: Seamlessly integrates external tools (like vector search and web search) with proper error handling and normalization.

-   **Human-in-the-Loop Ready**: Designed with interrupt capabilities for human review of responses, tool calls, and state editing without breaking the execution flow.

-   **LangGraph Platform Benefits**: Takes advantage of the LangGraph Platform API for:
    * Automatic durable execution with stateful persistence
    * Efficient background runs for long-running tasks
    * Elastic scaling for handling traffic bursts
    * Built-in monitoring and observability
    * Thread management for multi-user conversations

**System-Wide Patterns**:
-   **Subgraphs**: Organizes complex logic into reusable subgraphs with well-defined interfaces
-   **Structured Outputs**: Enforces consistent data formats across all agents
-   **Memory Management**: Manages conversation history and context effectively
-   **Web Frontend**: Provides a clean user interface built with standard web technologies

## Project Structure

```
multi_agent_system/
│
├── data/                      # Data storage
│   └── chroma_db/             # Vector database storage
│
├── docs/                      # Documentation files
│
├── examples/                  # Example usage patterns
│
├── src/
│   ├── backend/               # Backend server and agent logic
│   │   ├── agents/            # Agent implementations
│   │   │   ├── knowledge/     # Knowledge retrieval agent
│   │   │   ├── orchestrator/  # Central router logic
│   │   │   └── summarizer/    # Document summarization agent
│   │   ├── utils/             # Shared utilities
│   │   ├── app.py             # FastAPI application
│   │   ├── config.py          # Configuration management
│   │   └── routes.py          # API endpoints
│   │
│   └── static/                # Frontend assets
│       ├── js/                # JavaScript files
│       └── styles/            # CSS files
│
└── langgraph.json            # LangGraph configuration file
```

## Quick Start

1.  Clone the repository:
    ```bash
    git clone https://github.com/cgoncalves94/multi_agent_system.git
    cd multi_agent_system
    ```

2.  Install `uv` (recommended for faster, more reliable dependency management):
    ```bash
    # On Unix-like systems
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # On Windows PowerShell
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

3.  Create a virtual environment and install dependencies:
    ```bash
    # Create and activate virtual environment
    uv venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate

    # Install dependencies from pyproject.toml
    uv pip install -e .
    ```

4.  Set up your environment variables:
    ```bash
    cp src/backend/.env.example src/backend/.env
    # Edit .env with your API keys (see Configuration section)
    ```

5.  Run the application:
    ```bash
    uv run langgraph dev --no-browser
    ```
    The API and web interface will be available at `http://127.0.0.1:2024`, with the web interface mounted at `/static/index.html`.

## Development

### Dependencies
All project dependencies are managed in `pyproject.toml`:
-   **Core Dependencies**: LangChain, LangGraph, FastAPI, and related packages.
-   **Development Dependencies**: Tools for testing, linting, and formatting.

### Pre-commit Hooks
We use pre-commit hooks to ensure code quality. To set up:
```bash
pre-commit install
```
To run the hooks manually on all files:
```bash
pre-commit run --all-files
```

## Configuration

The system requires API keys and other settings defined in an `.env` file (copied from `.env.example`):
-   `OPENAI_API_KEY`: For LLM access and embeddings.
-   `TAVILY_API_KEY`: For the Tavily search API used by the Knowledge Agent.
-   `LANGSMITH_API_KEY`: For tracing and debugging with LangSmith.


## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/cgoncalves94/multi_agent_system/blob/main/LICENSE) file for details.
