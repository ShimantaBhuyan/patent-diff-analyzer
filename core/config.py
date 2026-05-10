import os
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""
    
    # App
    app_name: str = "Patent Diff Analyzer"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, alias="DEBUG")
    
    # Database
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5433/patent_diff",
        alias="DATABASE_URL"
    )
    
    # Vector
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")
    vector_index_type: str = Field(default="ivfflat", alias="VECTOR_INDEX_TYPE")
    
    # LLM
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.1, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=4096, alias="LLM_MAX_TOKENS")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    
    # Processing
    chunk_size: int = Field(default=512, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=100, alias="CHUNK_OVERLAP")
    max_file_size_mb: int = Field(default=50, alias="MAX_FILE_SIZE_MB")
    
    # Retrieval
    top_k_retrieval: int = Field(default=5, alias="TOP_K_RETRIEVAL")
    lexical_boost_weight: float = Field(default=0.3, alias="LEXICAL_BOOST_WEIGHT")
    
    # Async / Jobs
    use_job_queue: bool = Field(default=False, alias="USE_JOB_QUEUE")
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")
    job_timeout_seconds: int = Field(default=300, alias="JOB_TIMEOUT_SECONDS")
    
    # Observability
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    enable_request_timing: bool = Field(default=True, alias="ENABLE_REQUEST_TIMING")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
