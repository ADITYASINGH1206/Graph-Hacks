"""Configuration settings loaded from environment variables."""

import hashlib
import os
import re

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
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    agent_model: str = Field(default="gemini-2.5-pro", alias="AGENT_MODEL")
    extract_model: str = Field(default="gemini-2.5-flash", alias="EXTRACT_MODEL")
    falkordb_host: str = Field(default="localhost", alias="FALKORDB_HOST")
    falkordb_port: int = Field(default=6379, alias="FALKORDB_PORT")
    target_repo: str = Field(default="pallets/flask", alias="TARGET_REPO")
    module_depth: int = Field(default=2, alias="MODULE_DEPTH")
    # Canned, zero-network answers from the seed graph. Never enabled implicitly.
    dig_offline: bool = Field(default=False, alias="DIG_OFFLINE")
    # Comma-separated list of browser origins allowed to call the API.
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173", alias="CORS_ORIGINS"
    )

    @property
    def google_api_key(self) -> str:
        """Resolve Gemini / Google API key from GEMINI_API_KEY or GOOGLE_API_KEY."""
        return self.gemini_api_key or os.environ.get("GOOGLE_API_KEY", "")

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a clean list (empty entries dropped)."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def graph_name(self) -> str:
        """Derive canonical graph name dig_<owner>_<repo> from target_repo."""
        slug = self.target_repo.replace("/", "_").replace("-", "_").lower()
        return f"dig_{slug}"

    def memory_graph_name(self, user_id: str) -> str:
        """Derive a collision-free per-user memory graph name.

        A readable ASCII slug is combined with a short hash of the exact user id, so
        ids that only differ in punctuation or case ("a-b", "a_b", "A.B") can never
        share a memory graph.
        """
        raw = user_id.strip() or "anonymous"
        slug = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")[:32] or "user"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
        return f"mem_{slug}_{digest}"


settings = Settings()
