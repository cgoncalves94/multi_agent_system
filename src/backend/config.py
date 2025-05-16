"""Shared configuration settings for the multi-agent system."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# Define project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    """Environment configuration with validation."""

    # OpenAI
    openai_api_key: str = Field(default="", description="OpenAI API key")

    # Tavily
    tavily_api_key: str = Field(default="", description="Tavily API key")

    # LangChain
    langchain_api_key: str = Field(default="", description="LangChain API key")
    langchain_endpoint: str = Field(
        default="https://api.smith.langchain.com", description="LangChain endpoint"
    )
    langchain_tracing_v2: bool = Field(
        default=True, description="Enable LangChain tracing v2"
    )
    langchain_project_name: str = Field(
        default="multi_agent_system", description="LangChain project name"
    )

    # Storage Paths
    data_dir: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "data",
        description="Base directory for data storage",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def chroma_path(self) -> Path:
        """Full path for Chroma DB storage"""
        return self.data_dir / "chroma_db"

    def ensure_dirs(self) -> None:
        """Ensure all required directories exist."""
        dirs = [
            self.data_dir,
            self.chroma_path,
        ]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_env(cls) -> "Settings":
        """Load configuration from environment variables."""
        config = cls()
        config.ensure_dirs()
        return config

    # Shared model configuration
    def get_model(
        self,
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
            api_key=self.openai_api_key,
            model=model_name,
            temperature=temperature,
            streaming=streaming,
            **kwargs,
        )

    def get_embeddings(
        self, model_name: str = "text-embedding-3-small", **kwargs
    ) -> OpenAIEmbeddings:
        """Get a configured embeddings model instance.

        Args:
            model_name: Name of the embeddings model to use (default: text-embedding-3-small)
            **kwargs: Additional embeddings configuration options

        Returns:
            Configured OpenAIEmbeddings instance
        """
        return OpenAIEmbeddings(api_key=self.openai_api_key, model=model_name, **kwargs)


# Load environment configuration
settings = Settings.load_env()
