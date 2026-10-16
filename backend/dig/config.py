"""Configuration settings loaded from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for Decision Archaeologist."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    agent_model: str = Field(default="claude-sonnet-5-5", alias="AGENT_MODEL")
    extract_model: str = Field(default="claude-haiku-5-5", alias="EXTRACT_MODEL")
    falkordb_host: str = Field(default="localhost", alias="FALKORDB_HOST")
    falkordb_port: int = Field(default=6379, alias="FALKORDB_PORT")
    target_repo: str = Field(default="pallets/flask", alias="TARGET_REPO")
    module_depth: int = Field(default=2, alias="MODULE_DEPTH")

    @property
    def graph_name(self) -> str:
        """Derive canonical graph name dig_<owner>_<repo> from target_repo."""
        slug = self.target_repo.replace("/", "_").replace("-", "_").lower()
        return f"dig_{slug}"

    def memory_graph_name(self, user_id: str) -> str:
        """Derive per-user memory graph name mem_<user_id>."""
        slug = user_id.replace("/", "_").replace("-", "_").lower()
        return f"mem_{slug}"


settings = Settings()
