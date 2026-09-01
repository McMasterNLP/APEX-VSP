"""Application settings using Pydantic Settings."""

import json
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_cors_origins(v: str) -> List[str]:
    """Parse CORS_ORIGINS: JSON array string or comma-separated URLs."""
    if not v or not v.strip():
        return ["http://localhost:5173", "http://localhost:3000"]
    v = v.strip()
    if v.startswith("["):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            pass
    return [origin.strip() for origin in v.split(",") if origin.strip()]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    
    # Database
    database_url: str = Field(...)
    
    # JWT (legacy — kept for backward compatibility during migration)
    secret_key: str = Field(default="unused")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    
    # Supabase Auth
    supabase_jwt_secret: str = Field(...)
    
    # CORS: stored as string so env never triggers json.loads; parsed via helper.
    # Set CORS_ORIGINS to e.g. https://apex-client.onrender.com or ["https://..."]
    cors_origins_raw: str = Field(
        default='["http://localhost:5173","http://localhost:3000"]',
        alias="CORS_ORIGINS",
        description="Comma-separated URLs or JSON array",
    )

    @property
    def cors_origins(self) -> List[str]:
        """Parsed CORS origins based on cors_origins_raw."""
        return _parse_cors_origins(self.cors_origins_raw)
    
    # OpenAI
    openai_api_key: str = Field(...)
    openai_model_id: str = Field(default="gpt-4")
    
    # Google Gemini
    gemini_api_key: str = Field(...)
    gemini_model_id: str = Field(default="gemini-pro")
    
    # Storage
    supabase_url: str = Field(default="")
    supabase_service_role_key: str = Field(default="")
    supabase_storage_bucket: str = Field(default="")
    local_storage_path: str = Field(default="./storage")
    public_base_url: str = Field(default="http://localhost:8000")
    audio_cache_path: str = Field(default="./storage/cache/audio")
    audio_cache_max_bytes: int = Field(default=512 * 1024 * 1024)
    assistant_audio_ttl_seconds: int = Field(default=604800)
    assistant_audio_signed_url_ttl_seconds: int = Field(default=3600)
    
    # LLM Configuration
    default_llm_provider: str = Field(default="openai")
    ace_ct_allow_experimental_rubric: bool = Field(default=False)
    research_allow_live_evaluations: bool = Field(default=False)
    
    # TTS/ASR Configuration
    tts_provider: str = Field(default="openai")
    asr_provider: str = Field(default="whisper")
    openai_tts_model_id: str = Field(default="gpt-4o-mini-tts")
    openai_tts_voice: str = Field(default="coral")
    openai_tts_response_format: str = Field(default="mp3")
    openai_tts_instructions: str = Field(
        default="Speak naturally with warmth, empathy, and a calm bedside manner."
    )
    openai_tts_speed: float = Field(default=1.0)

    # Research export anonymization (deterministic session IDs)
    research_anon_salt: str = Field(default="research-anon-salt-change-in-production")

    # Plugin configuration
    patient_model_plugin: str = Field(
        default="plugins.patient_models.default_llm_patient:DefaultLLMPatientModel"
    )
    evaluator_plugin: str = Field(
        default="plugins.evaluators.apex_hybrid_evaluator:ApexHybridEvaluator"
    )
    metrics_plugins: list[str] = Field(
        default_factory=lambda: ["plugins.metrics.apex_metrics:ApexMetrics"]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("patient_model_plugin")
    @classmethod
    def _validate_patient_model_plugin(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError(
                f"Invalid plugin path '{v}'. Expected format 'module.path:ClassName'"
            )
        return v

    @field_validator("evaluator_plugin")
    @classmethod
    def _validate_evaluator_plugin(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError(
                f"Invalid plugin path '{v}'. Expected format 'module.path:ClassName'"
            )
        return v

    @field_validator("metrics_plugins")
    @classmethod
    def _validate_metrics_plugins(cls, v: list[str]) -> list[str]:
        for path in v:
            if ":" not in path:
                raise ValueError(
                    f"Invalid plugin path '{path}'. Expected format 'module.path:ClassName'"
                )
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_local_storage_path() -> Path:
    """Resolve the configured local storage directory."""
    settings = get_settings()
    return Path(settings.local_storage_path).resolve()


def get_audio_cache_path() -> Path:
    """Resolve the configured assistant audio cache directory."""
    settings = get_settings()
    return Path(settings.audio_cache_path).resolve()
 
