"""Configuration management for OpenClaw Triage."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeduplicationConfig(BaseSettings):
    """Configuration for deduplication engine."""
    
    model_config = SettingsConfigDict(env_prefix="TRIAGE_DEDUP_")
    
    similarity_threshold: float = Field(default=0.85, description="Cosine similarity threshold for duplicates")
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", description="Model for embeddings")
    vector_db_path: str = Field(default="./data/vectors", description="Path to vector database")
    max_candidates: int = Field(default=10, description="Max candidates to check for duplicates")


class BaseDetectionConfig(BaseSettings):
    """Configuration for base PR detection."""
    
    model_config = SettingsConfigDict(env_prefix="TRIAGE_BASE_")
    
    # Signal weights (should sum to ~1.0)
    weight_chronological: float = Field(default=0.25, description="Weight for being first")
    weight_quality: float = Field(default=0.30, description="Weight for code quality")
    weight_engagement: float = Field(default=0.20, description="Weight for discussion engagement")
    weight_author: float = Field(default=0.15, description="Weight for author reputation")
    weight_completeness: float = Field(default=0.10, description="Weight for solution completeness")
    
    min_quality_score: float = Field(default=0.6, description="Minimum quality to be considered base")
    min_test_coverage: float = Field(default=0.5, description="Minimum test coverage expected")


class ReviewConfig(BaseSettings):
    """Configuration for deep review."""
    
    model_config = SettingsConfigDict(env_prefix="TRIAGE_REVIEW_")
    
    llm_model: str = Field(default="claude-3-5-sonnet-20241022", description="LLM for deep review")
    max_tokens: int = Field(default=4000, description="Max tokens for review")
    temperature: float = Field(default=0.1, description="Temperature for review")
    enable_security_check: bool = Field(default=True, description="Enable security analysis")
    enable_performance_check: bool = Field(default=True, description="Enable performance analysis")


class VisionConfig(BaseSettings):
    """Configuration for vision alignment checking."""
    
    model_config = SettingsConfigDict(env_prefix="TRIAGE_VISION_")
    
    vision_doc_path: str = Field(default="./VISION.md", description="Path to vision document")
    alignment_threshold: float = Field(default=0.7, description="Minimum alignment score")
    auto_reject_threshold: float = Field(default=0.3, description="Auto-flag below this")


class GitHubConfig(BaseSettings):
    """Configuration for GitHub integration."""
    
    model_config = SettingsConfigDict(env_prefix="TRIAGE_GITHUB_")
    
    token: str = Field(default="", description="GitHub token")
    webhook_secret: str = Field(default="", description="Webhook secret for verification")
    app_id: str = Field(default="", description="GitHub App ID")
    private_key_path: str = Field(default="", description="Path to GitHub App private key")


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # App settings
    app_name: str = Field(default="openclaw-triage")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # Component configs
    dedup: DeduplicationConfig = Field(default_factory=DeduplicationConfig)
    base_detection: BaseDetectionConfig = Field(default_factory=BaseDetectionConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    
    # API settings
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8080)
    
    @classmethod
    def from_yaml(cls, path: Path) -> "Settings":
        """Load settings from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    def to_yaml(self, path: Path) -> None:
        """Save settings to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment/file."""
    global _settings
    _settings = Settings()
    return _settings
