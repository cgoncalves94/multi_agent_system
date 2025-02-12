"""Shared configuration settings for the multi-agent system."""

import os
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI, OpenAIEmbeddings


class EnvConfig(BaseModel):
    """Environment configuration with validation."""

    # OpenAI
    openai_api_key: str = Field(..., description="OpenAI API key")

    # Tavily
    tavily_api_key: str = Field(..., description="Tavily API key")

    # LangChain
    langchain_api_key: str = Field(..., description="LangChain API key")
    langchain_endpoint: str = Field(..., description="LangChain endpoint")
    langchain_tracing_v2: bool = Field(True, description="Enable LangChain tracing v2")
    langchain_project_name: str = Field(
        "multi_agent_system", description="LangChain project name"
    )

    # Storage Paths
    data_dir: str = Field(
        lambda: os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"),
        description="Base directory for data storage",
    )
    chroma_path: str = Field(
        "/deps/multi_agent_system/data/chroma_db",
        description="Path for Chroma DB storage",
    )

    @property
    def state_db_path(self) -> str:
        """Get the path for agent state SQLite database."""
        return os.path.join(self.data_dir, "state_db", "agent.db")

    @property
    def ensure_dirs(self) -> None:
        """Ensure all required directories exist."""
        dirs = [self.data_dir, self.chroma_path, os.path.dirname(self.state_db_path)]
        for dir_path in dirs:
            os.makedirs(dir_path, exist_ok=True)

    @classmethod
    def load_env(cls) -> "EnvConfig":
        """Load and validate environment variables."""
        config = cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
            langchain_api_key=os.getenv("LANGCHAIN_API_KEY", ""),
            langchain_endpoint=os.getenv(
                "LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"
            ),
            langchain_tracing_v2=os.getenv("LANGCHAIN_TRACING_V2", "true").lower()
            == "true",
            langchain_project_name=os.getenv("LANGCHAIN_PROJECT", "multi_agent_system"),
            chroma_path=os.getenv(
                "CHROMA_PATH", "/deps/multi_agent_system/data/chroma_db"
            ),
            data_dir=os.getenv(
                "DATA_DIR",
                os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"),
            ),
        )
        # Ensure all directories exist
        config.ensure_dirs
        return config


# Load environment configuration
env = EnvConfig.load_env()


# Shared model configuration
def get_model(
    model_name: str = "gpt-4o",
    temperature: float = 0.7,
    streaming: bool = True,
    **kwargs,
) -> ChatOpenAI:
    """Get a configured model instance with standard settings.

    Args:
        model_name: Name of the model to use (default: gpt-4o)
        temperature: Temperature setting (default: 0.7)
        streaming: Whether to enable streaming (default: True)
        **kwargs: Additional model configuration options

    Returns:
        Configured ChatOpenAI instance
    """
    return ChatOpenAI(
        api_key=env.openai_api_key,
        model=model_name,
        temperature=temperature,
        streaming=streaming,
        **kwargs,
    )


def get_embeddings(
    model_name: str = "text-embedding-3-small", **kwargs
) -> OpenAIEmbeddings:
    """Get a configured embeddings model instance.

    Args:
        model_name: Name of the embeddings model to use (default: text-embedding-3-small)
        **kwargs: Additional embeddings configuration options

    Returns:
        Configured OpenAIEmbeddings instance
    """
    return OpenAIEmbeddings(api_key=env.openai_api_key, model=model_name, **kwargs)
