# Multi-Agent System

A sophisticated multi-agent system implementing RAG (Retrieval-Augmented Generation) and Research capabilities using LangChain and LangGraph.

## Features (WIP)

- 🤖 Multiple specialized agents working together
- 📚 RAG Agent for document retrieval and context-aware responses
- 🔍 Research Agent for gathering and synthesizing information
- 🌐 Graph-based agent orchestration using LangGraph
- 💾 Vector store integration for efficient document retrieval

## Quick Start

1. Clone the repository
2. Install uv (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
3. Create virtual environment and install dependencies:
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -r requirements.txt
   ```
4. Set up your environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## Project Structure

```
.
├── agents/             # Agent implementations
│   ├── rag/           # RAG agent for document retrieval
│   └── researcher/    # Research agent for information gathering
```

## Status

🚧 **Work in Progress** 🚧

This project is under active development. Features and documentation will be updated regularly.

## License

MIT
