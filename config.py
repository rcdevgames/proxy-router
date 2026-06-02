from pydantic_settings import BaseSettings
from typing import Optional


class ModelConfig(BaseSettings):
    api_key: str
    base_url: str
    model: str
    enabled: bool = True
    supports_anthropic_format: bool = True  # Anthropic atau OpenAI format


class Settings(BaseSettings):
    port: int = 8080
    host: str = "0.0.0.0"
    request_timeout: int = 30
    max_retries: int = 1

    # Proxy authentication - required untuk akses
    proxy_api_key: str = ""

    # Model name yang di-expose ke client (HARUS exact match)
    model_name: str = "WAW-SUPER"

    # Model 1: Konektika (Priority 1)
    konektika_api_key: str = ""
    konektika_base_url: str = "https://konektika.web.id/v1"
    konektika_model: str = "kimi-pro"
    konektika_enabled: bool = True

    # Model 2: DataByte (Priority 2)
    databyte_api_key: str = ""
    databyte_base_url: str = "https://ai.databyte.co.id/anthropic/v1"
    databyte_model: str = "databyte-m1"
    databyte_enabled: bool = True

    # Model 3: GLM (Priority 3 - last resort)
    glm_api_key: str = ""
    glm_base_url: str = "https://api.z.ai/api/anthropic"
    glm_model: str = "GLM-4.7"
    glm_enabled: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def load_settings() -> Settings:
    return Settings()